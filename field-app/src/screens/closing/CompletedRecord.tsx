/**
 * The RECORD of one closed job — what FF-35 opens (FB-030, PO 2026-10-31;
 * decision log *"a technician's history is the last 14 days, kept on the
 * phone"*, coordinator judgment (3)). ONE component (B14 rule 43): the tablet
 * draws it beside the list (`tablet/layouts/CompletedLayout.tsx`) and a phone
 * pushes it as its own screen when a Completed card is tapped
 * (`CompletedScreen`, the `workOrderId` param).
 *
 * In order: the job and its outcome · the safety ticks · the steps · the
 * readings, each with its unit (hard rule 3) · the parts, by QUANTITY ONLY ·
 * what was done (the debrief the close carried) · who signed or refused, and
 * when · the photographs (`RecordPhoto`: the file while it is on the phone,
 * then loaded on tap from the server).
 *
 * ⚠ NO MONEY AND NO SPEED FIGURES (coordinator judgment (5)): no balance, no
 * part price, no labour or travel minutes. The tablet record drew labour and
 * travel until FB-030; they are gone from history on both form factors.
 *
 * Read from the handset only: the job's rows, and `body.record` (the debrief
 * and signer the close keeps, `workOrderClosed.recordOf`). A job refilled onto
 * a new phone fills the same rows from its bundle (`sync/extras.ts`).
 */
import { useIsFocused } from '@react-navigation/native';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Card, EmptyState, ListRow, RecordPhoto, StatusChip } from '../../components';
import { fromJson } from '../../db/json';
import * as closedQ from '../../db/queries/workOrderClosed';
import { useTheme } from '../../theme';
import { useWave } from '../onSite/fieldData';
import { acceptedAt } from '../onSite/job';
import { addressLines, formatStamp } from '../onSite/format';
import { useJobPort } from '../theJob/JobPort';
import { type JobView, loadJob } from '../theJob/jobModel';
import { hhmm } from '../theJob/format';
import { pathOf } from '../theJob/photoStamp';
import { OUTCOME_TONE } from './outcomeTone';

/**
 * The job, read from the handset, re-read when the screen comes back into
 * view. Through the job screens' port where the app provides one; else from
 * the closing wave's own data (`useWave`) — `loadJob` reads only the store,
 * whose technician it is, and the clock.
 */
export function useRecordView(workOrderId: string | null): JobView | null {
  const port = useJobPort();
  const w = useWave();
  const focused = useIsFocused();
  const version = port?.version ?? 0;
  return useMemo(() => {
    if (!workOrderId) return null;
    if (port) return loadJob(port, workOrderId);
    if (!w) return null;
    const reader = { db: w.db, captor: () => w.captor, clock: w.clock } as unknown as Parameters<typeof loadJob>[0];
    return loadJob(reader, workOrderId);
    // `version` and `focused` are re-read triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, w, workOrderId, version, focused]);
}

/** A reading's answer in words: its figure and unit, its text, or *Unable to read*. */
function readingValue(r: JobView['readings']['items'][number]['row'], unable: string): string {
  if (r.unable_to_read) return unable;
  if (r.value_text) return r.value_text;
  if (r.value !== null && r.value !== undefined && r.value !== '') return `${r.value} ${r.unit}`.trim();
  return '—';
}

export function CompletedRecord({
  workOrderId,
  head = true,
  testID = 'completed-record',
}: {
  workOrderId: string | null;
  /** The job's number and outcome; off where the pane's own title already says them (the tablet). */
  head?: boolean;
  testID?: string;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const view = useRecordView(workOrderId);
  if (!view) return <EmptyState title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID={`${testID}-none`} />;

  const order = view.order;
  const record = closedQ.recordOf(order);
  const accepted = acceptedAt({ extra: fromJson<Record<string, unknown>>(order.extra) ?? {} });
  const outcome = order.outcome ? t(`field.site.outcome.${order.outcome}`) : null;
  const where = addressLines(view.premise);
  const parts = [...view.materials.planned, ...view.materials.added].filter((m) => m.used > 0);
  const signer = record?.signer ?? null;

  return (
    <View style={{ gap: theme.space[3] }} testID={testID}>
      <Card testID={`${testID}-head`}>
        {head ? (
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[2] }}>
            <AppText variant="section">{order.number ?? ''}</AppText>
            {outcome ? <StatusChip tone={OUTCOME_TONE[order.outcome ?? ''] ?? 'neutral'}>{outcome}</StatusChip> : null}
          </View>
        ) : null}
        <AppText variant="body">{[view.customer?.name, where.line1].filter(Boolean).join(' · ')}</AppText>
        <AppText variant="label" tone="muted">
          {[order.type, order.closed_at ? formatStamp(order.closed_at) : null].filter(Boolean).join(' · ')}
        </AppText>
        <AppText variant="label" tone="muted" testID={`${testID}-accepted`}>
          {accepted ? t('field.ff35.acceptedByOffice') : t('field.ff35.waitingForOffice')}
        </AppText>
      </Card>

      {view.safety.items.length > 0 ? (
        <Card title={t('field.record.safety')} testID={`${testID}-safety`}>
          {view.safety.items.map((row, i) => (
            <ListRow key={row.id} divider={i > 0} label={row.label} value={row.state ? '✓' : '—'} />
          ))}
        </Card>
      ) : null}

      {view.tasks.items.length > 0 ? (
        <Card title={t('field.record.steps')} testID={`${testID}-steps`}>
          {view.tasks.items.map((task, i) => (
            <ListRow
              key={task.row.id}
              divider={i > 0}
              label={task.row.label}
              detail={task.row.added_in_field ? t('field.record.addedInField') : undefined}
              value={task.done ? '✓' : t('field.record.notDone')}
            />
          ))}
        </Card>
      ) : null}

      {view.readings.items.length > 0 ? (
        <Card title={t('field.record.readings')} testID={`${testID}-readings`}>
          {view.readings.items.map((r, i) => (
            <ListRow
              key={r.row.id}
              divider={i > 0}
              label={r.row.prompt}
              value={readingValue(r.row, t('field.record.unableToRead'))}
              testID={`${testID}-reading-${i}`}
            />
          ))}
        </Card>
      ) : null}

      {parts.length > 0 ? (
        <Card title={t('field.record.parts')} testID={`${testID}-parts`}>
          {parts.map((m, i) => (
            // Quantity only — never a price (no money in history).
            <ListRow key={m.row.id} divider={i > 0} label={m.row.label} value={`× ${m.used}`} />
          ))}
        </Card>
      ) : null}

      {record && (record.problem || record.done) ? (
        <Card title={t('field.record.whatWasDone')} testID={`${testID}-debrief`}>
          {record.problem ? <ListRow label={t('field.record.problem')} detail={record.problem} /> : null}
          {record.done ? <ListRow divider={!!record.problem} label={t('field.record.done')} detail={record.done} /> : null}
        </Card>
      ) : null}

      <Card title={t('field.record.signature')} testID={`${testID}-signature`}>
        <AppText variant="body">
          {!signer
            ? t('field.record.noSignature')
            : signer.kind === 'signed'
              ? t('field.record.signedBy', { name: signer.name, time: signer.at ? formatStamp(signer.at) : '' })
              : t('field.record.notSigned', { reason: signer.reason, time: signer.at ? formatStamp(signer.at) : '' })}
        </AppText>
      </Card>

      {view.photos.length > 0 ? (
        <Card title={t('field.record.photos')} testID={`${testID}-photos`}>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[2] }}>
            {view.photos.map((p) => (
              <RecordPhoto
                key={p.id}
                photoId={p.id}
                kind="job"
                path={pathOf(p)}
                label={t('field.job.photoAt', { time: hhmm(p.captured_at) })}
                caption={hhmm(p.captured_at)}
                testID={`${testID}-photo-${p.id}`}
              />
            ))}
          </View>
        </Card>
      ) : null}
    </View>
  );
}
