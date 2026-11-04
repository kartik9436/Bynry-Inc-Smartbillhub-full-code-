/**
 * The can't-read reason picker — ONE component for the route reading (RW-17)
 * and the job reading (FF-20 *Unable to read*).
 *
 * DEF-MET-10609 — decision log 2026-10-26, PO verbatim *"yes do it"*: ONE list
 * of reasons for meter-reading routes AND job readings, so the technician sees
 * the same words everywhere. The list is the utility's own (R82,
 * `metering.CantReadReason`, managed in Settings → Reference data → Readings)
 * and lives on the phone under `LIST_KEYS.cantRead`, written by BOTH downloads:
 * the route download (`sync/routes.ts`) and a job's bundle (`sync/extras.ts`,
 * `cant_read_reasons`), so a technician with no route still has it offline.
 *
 * B14 rule 43: this was 20 lines inside RW-17's screen, importable by nothing;
 * it is a component so FF-20 uses the same one rather than a copy.
 */
import { useTranslation } from 'react-i18next';

import { Notice, RadioList } from '../../components';
import type { TenantDb } from '../../db/database';
import * as settingsQ from '../../db/queries/settings';
import { asList, type ListEntry, LIST_KEYS } from './records';

/** The reasons on this phone, in the utility's order — or null before any download. */
export function cantReadReasons(db: TenantDb): ListEntry[] | null {
  return asList(settingsQ.get(db, LIST_KEYS.cantRead));
}

export function CantReadReasonPicker(props: {
  reasons: readonly ListEntry[] | null;
  selected: string | null;
  onSelect: (code: string) => void;
  testID?: string;
}) {
  const { t } = useTranslation();
  if (!props.reasons || props.reasons.length === 0) {
    return (
      <Notice tone="warning" testID="no-reasons">
        {t('field.reads.rw17.noList')}
      </Notice>
    );
  }
  return (
    <RadioList
      label={t('field.reads.rw17.why')}
      options={props.reasons.map((r) => ({ id: r.code, label: r.label }))}
      selected={props.selected}
      onSelect={props.onSelect}
      testID={props.testID ?? 'reasons'}
    />
  );
}
