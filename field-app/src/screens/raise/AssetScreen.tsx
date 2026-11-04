/**
 * FF-39 Asset — one meter: what it is, its identity, where it is, its
 * sub-meters and its last read (US-FLD-010 TC-2; R15 meters and sub-meters
 * only). Everything from the handset, so it opens offline.
 *
 * The meter comes from the `assetId` param (Scan, Search) or, failing that,
 * the job's own meter (`workOrderId`). The drawn header icons — search
 * (FF-41) and scan (FF-38) — sit at the top of the page; *Service history*
 * opens FF-40.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Kicker } from '../../components/AppText';
import { Button, IconButton } from '../../components/Button';
import { Card } from '../../components/Card';
import { FactGrid } from '../../components/Facts';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { ScreenFrame } from '../../components/ScreenFrame';
import { StatusChip } from '../../components/StatusChip';
import * as assetQ from '../../db/queries/asset';
import * as familyQ from '../../db/queries/assetFamily';
import * as premiseQ from '../../db/queries/premise';
import * as workOrderQ from '../../db/queries/workOrder';
import { useTheme } from '../../theme';
import { NotOnPhone, useHeader, type WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParam, type Wave } from '../onSite/fieldData';
import { addressLines, formatDate, formatFigure } from '../onSite/format';
import { extraOf, lastRead, visitsOf } from './history';

export function assetFor(w: Wave, assetId: string | null, workOrderId: string | null): assetQ.AssetRow | null {
  if (assetId) return assetQ.get(w.db, assetId) ?? null;
  const order = workOrderId ? workOrderQ.getMine(w.s, workOrderId) : undefined;
  return order?.asset_id ? (assetQ.get(w.db, order.asset_id) ?? null) : null;
}

export function AssetScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const workOrderId = useParam('workOrderId');
  const asset = assetFor(w, useParam('assetId'), workOrderId);
  useHeader({ title: asset?.serial ?? null });
  if (!asset) return <NotOnPhone />;

  const premise = asset.premise_id ? premiseQ.get(w.db, asset.premise_id) : undefined;
  const where = addressLines(premise);
  const subs = familyQ.children(w.db, asset.id);
  const { installedAt, locationNote } = extraOf(asset.extra);
  const last = lastRead(visitsOf(asset.history));
  const carry = { assetId: asset.id, ...(workOrderId ? { workOrderId } : {}) };

  return (
    <ScreenFrame
      footer={
        <Button variant="primary" grow onPress={() => goTo(navigation, 'FF-40', carry)} testID="door-FF-40">
          {t('field.ff39.history')}
        </Button>
      }
    >
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', gap: theme.space[2] }}>
        <IconButton label={t('field.ff39.search')} onPress={() => goTo(navigation, 'FF-41')} testID="door-FF-41">
          <Mark name="search" />
        </IconButton>
        <IconButton label={t('field.ff39.scan')} onPress={() => goTo(navigation, 'FF-38', workOrderId ? { workOrderId } : undefined)} testID="door-FF-38">
          <Mark name="scan" />
        </IconButton>
      </View>

      <Card>
        <Kicker tone="brand">{t('field.ff39.kind', { service: asset.service ?? '' })}</Kicker>
        <AppText variant="title" testID="asset-model">
          {[asset.model, asset.size].filter(Boolean).join(' · ')}
        </AppText>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
          <StatusChip tone={asset.status === 'active' ? 'success' : 'warning'}>
            {asset.status === 'active' ? t('field.ff39.installed') : t('field.site.asset.pending')}
          </StatusChip>
          {installedAt ? (
            <AppText variant="label" tone="muted">
              {t('field.ff39.since', { date: formatDate(installedAt) })}
            </AppText>
          ) : null}
        </View>
      </Card>

      <Card title={t('field.ff39.identity')}>
        <FactGrid
          testID="identity"
          facts={[
            { label: t('field.ff39.serial'), value: asset.serial ?? '—' },
            { label: t('field.ff39.badge'), value: asset.badge ?? '—' },
            { label: t('field.ff39.deviceId'), value: asset.device_id ?? '—' },
            { label: t('field.ff39.size'), value: asset.size ?? '—' },
          ]}
        />
      </Card>

      <Card title={t('field.ff39.where')}>
        <AppText variant="body">{where.line1}</AppText>
        <AppText variant="body">{where.line2}</AppText>
        {locationNote ? (
          <AppText variant="label" tone="muted">
            {locationNote}
          </AppText>
        ) : null}
      </Card>

      {subs.length > 0 ? (
        <Card title={t('field.ff39.subMeters')} testID="sub-meters">
          {subs.map((sub, i) => {
            const subLast = lastRead(visitsOf(sub.history));
            return (
              <ListRow
                key={sub.id}
                divider={i > 0}
                label={sub.serial ?? '—'}
                value={subLast?.reading ? `${formatFigure(subLast.reading.value)} ${subLast.reading.unit}` : undefined}
                onPress={() => goTo(navigation, 'FF-39', { assetId: sub.id })}
                testID={`sub-${sub.serial ?? sub.id}`}
              />
            );
          })}
        </Card>
      ) : null}

      {last?.reading ? (
        <Card title={t('field.ff39.lastRead')} testID="last-read">
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2] }}>
            <AppText variant="title">{formatFigure(last.reading.value)}</AppText>
            <AppText variant="body" tone="muted">
              {last.reading.unit}
            </AppText>
          </View>
          <AppText variant="label" tone="muted">
            {[formatDate(last.date), last.who].filter(Boolean).join(' · ')}
          </AppText>
        </Card>
      ) : null}
    </ScreenFrame>
  );
}
