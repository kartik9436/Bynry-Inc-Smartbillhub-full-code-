/**
 * FF-22 Compare — before and after, one above the other or side by side
 * (US-FLD-027 TC-2: *"Before 09:18 and after 09:52 · 34 min later, stacked or
 * side by side"*). Side by side is the tablet's default, where the width is.
 *
 * Which two: the first and the last photograph of the step or reading opened
 * from FF-21 (`proofId`), else of the first one on the job with two or more.
 * The template's own words label them when it gives them (`photo_labels`).
 *
 * ⚠ The board's share button is not drawn: sharing a photograph needs a
 * package this build does not have (`expo-sharing`), and a dead control is
 * worse than none (hard-won law 2's mirror). Reported.
 *
 * Built from `phone/FF-22-compare.png` / `tablet/FF-22-T-before-and-after.png`.
 * Door: back → FF-21.
 */
import { useRoute } from '@react-navigation/native';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, ChoiceChips, Kicker, Notice, PhotoThumb } from '../../components';
import type { OrderPhotoRow } from '../../db/queries/jobScreens';
import { useSideBySide } from '../../tablet/columns';
import { useTheme } from '../../theme';
import { hhmm, minutesBetween } from './format';
import { JobScreen } from './JobScreen';
import { pathOf, stampOfRow } from './photoStamp';
import { useOpenJob } from './useJob';

export function Compare() {
  const { t } = useTranslation();
  const theme = useTheme();
  const route = useRoute();
  // Side by side only where the pane holds two columns of 260 (R122) — in
  // the tablet's T3 content pane it opens stacked; the switch still offers both.
  const sideBySide = useSideBySide();
  const [layout, setLayout] = useState<'stacked' | 'side'>(sideBySide ? 'side' : 'stacked');
  const { port, view } = useOpenJob();
  const proofId = (route.params as { proofId?: string } | undefined)?.proofId ?? null;

  const groups: { id: string; photos: OrderPhotoRow[]; labels: string[] }[] = view
    ? [
        ...view.tasks.items.map((x) => ({ id: x.row.id, photos: x.photos, labels: x.detail.photo_labels ?? [] })),
        ...view.readings.items.map((r) => ({ id: r.row.id, photos: r.photos, labels: [] as string[] })),
      ]
    : [];
  const group = groups.find((g) => g.id === proofId && g.photos.length >= 2) ?? groups.find((g) => g.photos.length >= 2) ?? null;
  const before = group?.photos[0] ?? null;
  const after = group ? (group.photos[group.photos.length - 1] ?? null) : null;
  const order = view?.order.number ?? '';
  const who = (p: OrderPhotoRow) => (p.captured_by === port?.captor().capturedBy ? port.displayName : p.captured_by);

  const panel = (p: OrderPhotoRow, kicker: string, line: string, testID: string) => (
    <View style={{ flexGrow: 1, flexBasis: 0, gap: theme.space[2] }} testID={testID}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        <Kicker tone="brand">{kicker}</Kicker>
        <AppText variant="label" tone="muted">
          {line}
        </AppText>
      </View>
      <PhotoThumb size="large" path={pathOf(p)} label={`${kicker}, ${hhmm(p.captured_at)}`} stamp={stampOfRow(t, p, who(p), order, port?.tenantName ?? '')} />
    </View>
  );

  return (
    <JobScreen
      id="FF-22"
      title={t('field.screen.ff22')}
      back={{ to: 'FF-21', label: t('field.ff22.backToPhotos') }}
      footer={
        <ChoiceChips
          label={t('field.ff22.layout')}
          fill
          active={layout}
          onSelect={(id) => setLayout(id as 'stacked' | 'side')}
          segments={[
            { id: 'stacked', label: t('field.ff22.stacked') },
            { id: 'side', label: t('field.ff22.side') },
          ]}
          testID="compare-layout"
        />
      }
    >
      {before && after ? (
        <View style={{ flexDirection: layout === 'side' ? 'row' : 'column', gap: theme.space[3] }} testID={`compare-${layout}`}>
          {panel(before, group?.labels[0] ?? t('field.ff22.before'), hhmm(before.captured_at), 'compare-before')}
          {panel(
            after,
            group?.labels[group.labels.length - 1] && group.labels.length > 1 ? (group.labels[group.labels.length - 1] ?? '') : t('field.ff22.after'),
            `${hhmm(after.captured_at)} · ${t('field.ff22.later', { count: minutesBetween(before.captured_at, after.captured_at) })}`,
            'compare-after',
          )}
        </View>
      ) : (
        <Notice tone="info" testID="compare-none">
          {t('field.ff22.none')}
        </Notice>
      )}
    </JobScreen>
  );
}
