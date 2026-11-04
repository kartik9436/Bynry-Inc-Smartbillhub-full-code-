/**
 * FF-40 History — who touched this meter, what they found, what they did and
 * what they used, from the copy on the phone (US-FLD-019; R116: the history
 * is one blob, rendered whole, never queried across assets). Works offline
 * (TC-2), because nothing here asks the server.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Card } from '../../components/Card';
import { FactLines } from '../../components/Facts';
import { ScreenFrame } from '../../components/ScreenFrame';
import { StatusChip } from '../../components/StatusChip';
import { Pickable } from '../../tablet/Pickable';
import { usePick } from '../../tablet/selection';
import type { StatusTone } from '../../theme';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from '../onSite/common';
import { useParam } from '../onSite/fieldData';
import { formatDate, formatFigure } from '../onSite/format';
import { assetFor } from './AssetScreen';
import { visitsOf } from './history';

export const TONE: Record<string, StatusTone> = {
  passed: 'success',
  partially_done: 'warning',
  failed: 'danger',
  waiting_on_someone_else: 'warning',
};
export const KNOWN = Object.keys(TONE);

export function AssetHistoryScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const pick = usePick();
  const asset = assetFor(w, useParam('assetId'), useParam('workOrderId'));
  if (!asset) return <NotOnPhone />;
  const visits = visitsOf(asset.history);
  const none = t('field.ff40.none');

  return (
    <ScreenFrame
      header={
        <View>
          <AppText variant="body" weight="heavy">
            {[asset.serial, asset.model].filter(Boolean).join(' · ')}
          </AppText>
          <AppText variant="label" tone="muted" testID="visit-count">
            {t('field.ff40.cached', { count: visits.length })}
          </AppText>
        </View>
      }
    >
      {visits.map((v, i) => (
        <Card
          key={`${v.date}-${i}`}
          testID={`visit-${i}`}
          style={pick.isPicked(String(i)) ? { borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis } : undefined}
        >
          {/* FF-40 T: beside the visit, the card's head picks it. */}
          <Pickable id={String(i)} bare label={`${formatDate(v.date)}, ${v.work}`} testID={`visit-${i}-pick`}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: theme.space[2] }}>
              <AppText variant="body" weight="heavy">
                {formatDate(v.date)}
              </AppText>
              {v.outcome ? (
                <StatusChip tone={TONE[v.outcome] ?? 'neutral'}>
                  {KNOWN.includes(v.outcome) ? t(`field.site.outcome.${v.outcome}`) : v.outcome}
                </StatusChip>
              ) : null}
            </View>
            <AppText variant="section">{v.work}</AppText>
          </Pickable>
          <FactLines
            facts={[
              { label: t('field.ff40.problem'), value: v.problem ?? none },
              {
                label: t('field.ff40.done'),
                value: [v.done, v.reading ? `${formatFigure(v.reading.value)} ${v.reading.unit}` : null].filter(Boolean).join(' · ') || none,
              },
              { label: t('field.ff40.parts'), value: v.parts ?? none },
              {
                label: t('field.ff40.who'),
                value: [v.who, v.minutes !== null ? t('field.ff40.minutes', { count: v.minutes }) : null].filter(Boolean).join(' · ') || none,
              },
            ]}
          />
        </Card>
      ))}
      {visits.length === 0 ? (
        <AppText variant="body" tone="muted">
          {t('field.ff40.noVisits')}
        </AppText>
      ) : null}
    </ScreenFrame>
  );
}
