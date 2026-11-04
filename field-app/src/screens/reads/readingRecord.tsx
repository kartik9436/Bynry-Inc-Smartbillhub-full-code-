/**
 * RW-28's drill (FB-030, PO 2026-10-31; decision log *"a technician's history
 * is the last 14 days, kept on the phone"*, coordinator judgment (4)): from a
 * route into each reading taken on it, and one reading's record.
 *
 *   RouteReadings — the readings taken on one route, in the order taken,
 *                   paged 50 at a time (*Show more*; no cap). Each opens its
 *                   record. Shown on RW-27, the route RW-28's card opens.
 *   ReadingRecord — one reading: the meter, the address, the figure WITH ITS
 *                   UNIT (hard rule 3), the status — with FB-022's *Lower than
 *                   last* flag and the can't-read reason — the note, the
 *                   photographs (`RecordPhoto`: the file for 3 days, then on
 *                   tap from the server) and the time. RW-28 renders it when
 *                   opened with a `readId`.
 *
 * Each is a component (B14 rule 43). What was read, never how fast (R120): no
 * rate, no per-hour count, no ranking.
 */
import { StackActions, useNavigation } from '@react-navigation/native';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, Kicker, ListRow, Notice, RecordPhoto, StatusChip } from '../../components';
import * as walkQ from '../../db/queries/readsWalk';
import { useTheme } from '../../theme';
import { formatStamp } from '../onSite/format';
import { hhmm } from '../theJob/format';
import { cantReadReasons } from './CantReadReasonPicker';
import { group, verdict } from './figures';
import { PressCard, Spread } from './parts';
import { useLive } from './ReadsScreen';
import { meterName } from './records';
import { useReads } from './services';

export const READINGS_PAGE = 50;

/** FB-022's flag: the server's word on a refilled reading, else the phone's own comparison. */
export function isLowerThanLast(m: Pick<walkQ.MeterRead, 'lower_than_last' | 'value' | 'previous_value'>): boolean {
  if (m.lower_than_last === 1) return true;
  if (m.lower_than_last === 0) return false;
  return !!m.value && verdict(m.value, m.previous_value, null, null) === 'below_previous';
}

function statusKey(m: Pick<walkQ.MeterRead, 'reader_status'>): string {
  if (m.reader_status === 'could_not_read') return 'field.reads.status.couldNot';
  if (m.reader_status === 'read_with_problem') return 'field.reads.status.withProblem';
  return 'field.reads.status.read';
}

/** The readings taken on one route — each opens its record (RW-28 with a `readId`). */
export function RouteReadings({ routeId }: { routeId: string }) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { s } = useReads();
  const [pages, setPages] = useState(1);
  const rows = useLive(() => walkQ.takenOnRoute(s, routeId, READINGS_PAGE * pages + 1), [routeId, pages]);
  const shown = rows.slice(0, READINGS_PAGE * pages);
  if (shown.length === 0) return null;
  return (
    <View testID="route-readings">
      <Kicker>{t('field.reads.rw28.readings')}</Kicker>
      {shown.map((m, i) => (
        <PressCard
          key={m.id}
          label={meterName(m)}
          onPress={() => navigation.dispatch(StackActions.push('RW-28', { readId: m.id }))}
          testID={`reading-${i}`}
        >
          <Spread>
            <View style={{ flexShrink: 1 }}>
              <AppText variant="body" weight="heavy">
                {meterName(m)}
              </AppText>
              <AppText variant="label" tone="muted">
                {[m.address_line, m.captured_at ? hhmm(m.captured_at) : null].filter(Boolean).join(' · ')}
              </AppText>
            </View>
            <AppText variant="body">{m.value !== null ? `${group(m.value)} ${m.unit}` : t(statusKey(m))}</AppText>
          </Spread>
        </PressCard>
      ))}
      {rows.length > shown.length ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="readings-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
    </View>
  );
}

/** One reading's record. */
export function ReadingRecord({ readId }: { readId: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { s, services } = useReads();
  const db = services.db;
  const m = useLive(() => walkQ.meter(s, readId) ?? null, [readId]);
  const photos = useLive(() => walkQ.readingPhotos(s, readId), [readId]);
  if (!m) return <Notice tone="info">{t('field.reads.common.noMeter')}</Notice>;
  const reason = m.no_read_reason ? (cantReadReasons(db)?.find((r) => r.code === m.no_read_reason)?.label ?? m.no_read_reason) : null;
  const lower = isLowerThanLast(m);
  return (
    <View style={{ gap: theme.space[3] }} testID="reading-record">
      <Card>
        <AppText variant="section">{meterName(m)}</AppText>
        <AppText variant="body">{m.address_line ?? ''}</AppText>
      </Card>
      <Card testID="reading-record-facts">
        <ListRow label={t('field.reads.rw28.value')} value={m.value !== null ? `${group(m.value)} ${m.unit}` : '—'} testID="reading-record-value" />
        <ListRow
          divider
          label={t('field.reads.rw28.status')}
          value={
            <View style={{ alignItems: 'flex-end', gap: theme.space[1] }}>
              <AppText variant="body">{t(statusKey(m))}</AppText>
              {lower ? (
                <StatusChip tone="warning" testID="reading-record-lower">
                  {t('field.reads.rw28.lowerThanLast')}
                </StatusChip>
              ) : null}
            </View>
          }
        />
        {reason ? <ListRow divider label={t('field.reads.rw28.reason')} value={reason} testID="reading-record-reason" /> : null}
        {m.remark ? <ListRow divider label={t('field.reads.rw28.note')} detail={m.remark} testID="reading-record-note" /> : null}
        <ListRow divider label={t('field.reads.rw28.time')} value={m.captured_at ? formatStamp(m.captured_at) : '—'} />
      </Card>
      {photos.length > 0 ? (
        <Card title={t('field.record.photos')} testID="reading-record-photos">
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[2] }}>
            {photos.map((p) => (
              <RecordPhoto
                key={p.id}
                photoId={p.id}
                kind="route"
                path={p.file_deleted ? null : p.local_path || null}
                label={t('field.job.photoAt', { time: hhmm(p.captured_at) })}
                caption={hhmm(p.captured_at)}
                testID={`reading-record-photo-${p.id}`}
              />
            ))}
          </View>
        </Card>
      ) : null}
    </View>
  );
}
