/**
 * FF-25 Customer — who lives here, what is on supply, this visit; and for an
 * employee the balance with its age (US-FLD-012; tablet board FF-25 T).
 *
 *   R16 — the app reads money and never writes it: no tender, no staging.
 *   R17 — older than 5 minutes is warned, never blocked.
 *   R26 — a contractor sees the name, not the money. The phone board is drawn
 *         as a contractor sees it (the *Contractor* chip, no balance); the
 *         tablet board adds the BALANCE card an employee sees.
 *
 * Doors (navigation/doors.ts): FF-15 the job, FF-26 Restoration, FF-27
 * Disconnect — the last two drawn as buttons on the tablet board.
 */
import { useTranslation } from 'react-i18next';
import { Linking, View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { ScreenFrame } from '../../components/ScreenFrame';
import { StatusChip } from '../../components/StatusChip';
import { useTheme } from '../../theme';
import { jobPoint, pointUrl } from '../theJob/jobPoint';
import { BalanceCard } from './BalanceCard';
import { useHeader, type WaveScreenProps, NotOnPhone } from './common';
import { goTo, useNav, useJobId } from './fieldData';
import { addressLines, formatClock } from './format';
import { loadJob, moneyRole, showsOf } from './job';
import { useMoney } from './useMoney';

export function CustomerScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const workOrderId = useJobId();
  const job = loadJob(w, workOrderId);
  // FB-023 F3: the chip says *Contractor* only when the server said so; a
  // phone that has not learned the role yet hides the money and says nothing.
  const role = moneyRole(w);
  const employee = role === 'employee';
  const money = useMoney(w, job?.order.id ?? null, employee);
  useHeader({ chip: role === 'contractor' ? t('field.ff25.contractor') : null });

  if (!job) return <NotOnPhone />;
  const { order, premise, customer, asset } = job;
  // FB-023 F4/F6 — what the job's template lets the technician see.
  const shows = showsOf(job);
  const where = addressLines(premise);
  const phone = shows.appointment ? (customer?.phone ?? null) : null;
  // DEF-FLD-10582: the job's own point (a unit's, else its building's).
  const point = jobPoint(order.extra, premise);
  const params = { workOrderId: order.id };
  const window =
    shows.appointment && order.window_start && order.window_end ? `${formatClock(order.window_start)}–${formatClock(order.window_end)}` : null;

  return (
    <ScreenFrame
      footer={
        <Button variant="primary" grow onPress={() => goTo(navigation, 'FF-15', params)} testID="door-FF-15">
          {t('field.ff25.backToJob')}
        </Button>
      }
    >
      <Card>
        <AppText variant="title" testID="customer-name">
          {customer?.name ?? t('field.ff25.noName')}
        </AppText>
        <View>
          <AppText variant="body">{where.line1}</AppText>
          <AppText variant="body">{where.line2}</AppText>
        </View>
        {shows.accountSummary && customer?.account_number ? (
          <AppText variant="label" tone="muted">
            {t('field.ff25.account', { account: customer.account_number })}
          </AppText>
        ) : null}
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          {shows.appointment ? (
          <Button size="sm" grow disabled={!phone} onPress={() => phone && void Linking.openURL(`tel:${phone}`)} testID="call">
            {t('field.ff25.call')}
          </Button>
          ) : null}
          <Button size="sm" grow disabled={!point} onPress={() => point && void Linking.openURL(pointUrl(point, premise?.address_line ?? null))} testID="navigate">
            {t('field.ff25.navigate')}
          </Button>
        </View>
      </Card>

      {employee && shows.balancePayments ? <BalanceCard money={money} now={w.clock.now()} /> : null}

      {shows.assetCard ? (
      <Card title={t('field.ff25.service')} testID="service-card">
        {asset ? (
          <>
            <ListRow
              label={asset.service ?? t('field.ff25.serviceUnknown')}
              value={
                <StatusChip tone={asset.status === 'active' ? 'success' : 'warning'}>
                  {asset.status === 'active' ? t('field.site.asset.active') : t('field.site.asset.pending')}
                </StatusChip>
              }
            />
            <ListRow divider label={t('field.ff25.meter')} value={asset.serial ?? '—'} />
          </>
        ) : (
          <AppText variant="body" tone="muted">
            {t('field.ff25.noMeter')}
          </AppText>
        )}
      </Card>
      ) : null}

      <Card title={t('field.ff25.thisVisit')} testID="visit-card">
        <AppText variant="body">{[order.type, shows.assetCard ? asset?.size : null].filter(Boolean).join(' · ')}</AppText>
        <AppText variant="label" tone="muted">
          {[order.number, window].filter(Boolean).join(' · ')}
        </AppText>
      </Card>

      <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
        <Button size="sm" grow onPress={() => goTo(navigation, 'FF-26', params)} testID="door-FF-26">
          {t('field.ff25.restoration')}
        </Button>
        <Button size="sm" grow onPress={() => goTo(navigation, 'FF-27', params)} testID="door-FF-27">
          {t('field.ff25.disconnect')}
        </Button>
      </View>
    </ScreenFrame>
  );
}
