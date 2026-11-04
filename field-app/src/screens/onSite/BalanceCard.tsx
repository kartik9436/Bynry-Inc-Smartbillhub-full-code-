/**
 * The balance with its age and *Check now* — FF-25 (tablet BALANCE) and
 * FF-27 (the amber *BALANCE IS 3 DAYS OLD* card that turns green). One
 * component because it is one rule (R17): older than five minutes is warned,
 * never blocked, and the figure always says how old it is.
 *
 * Read only (R16): nothing on it writes money.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DotLine } from '../../components/DotLine';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { StatusChip } from '../../components/StatusChip';
import { useTheme } from '../../theme';
import { formatDay, formatMoney, formatStamp, isZeroAmount } from './format';
import { MONEY_FRESH_MINUTES, type MoneyReading } from './money';
import { ageText, type MoneyState } from './useMoney';

const NOTICE_TIERS = new Set(['tier_1_reminder', 'tier_2_10_day', 'tier_3_48_hour']);

/**
 * The payment facts under the balance (FB-023): the latest payment with its
 * state — *Posted* until the bank clears it, never *Cleared* before (F2,
 * DEF-FLD-10792) — and, on a DISCONNECT job only, the payment plan and the
 * latest disconnect notice (F5; the server sends them on no other job).
 * Never card or bank details: the wire carries none.
 */
export function PaymentFacts({ reading }: { reading: MoneyReading }) {
  const { t } = useTranslation();
  const paid = reading.latestPayment ?? null;
  const plan = reading.disconnect?.plan ?? null;
  const notice = reading.disconnect?.notice ?? null;
  if (!paid && !plan && !notice) return null;
  return (
    <View testID="payment-facts">
      {paid ? (
        <ListRow
          label={t('field.money.lastPaid', { amount: formatMoney(paid.amount, reading.currency), day: formatDay(paid.at) })}
          detail={paid.method ?? undefined}
          value={
            <StatusChip tone={paid.state === 'cleared' ? 'success' : 'warning'} testID="payment-state">
              {paid.state === 'cleared' ? t('field.money.cleared') : t('field.money.posted')}
            </StatusChip>
          }
          testID="last-payment"
        />
      ) : null}
      {plan ? (
        <ListRow
          divider={!!paid}
          label={t('field.money.plan.label')}
          value={
            <StatusChip tone={plan === 'behind' ? 'danger' : 'success'} testID="plan-status">
              {plan === 'behind' ? t('field.money.plan.behind') : t('field.money.plan.onTrack')}
            </StatusChip>
          }
          testID="payment-plan"
        />
      ) : null}
      {notice ? (
        <ListRow
          divider={!!paid || !!plan}
          label={t('field.money.notice.label')}
          detail={[
            NOTICE_TIERS.has(notice.tier) ? t(`field.money.notice.${notice.tier}`) : t('field.money.notice.other'),
            // A business DATE: read at local noon so no time zone moves its day.
            formatDay(/^\d{4}-\d{2}-\d{2}$/.test(notice.issuedOn) ? `${notice.issuedOn}T12:00:00` : notice.issuedOn),
            notice.amount ? formatMoney(notice.amount, reading.currency) : null,
          ]
            .filter(Boolean)
            .join(' · ')}
          testID="disconnect-notice"
        />
      ) : null}
    </View>
  );
}

export function BalanceCard(props: { money: MoneyState; now: Date; testID?: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { reading, stale, checking, failed, check } = props.money;
  const paid = reading !== null && !stale && isZeroAmount(reading.balance);
  const tone = reading === null || stale ? 'warning' : 'plain';
  const title =
    reading === null
      ? t('field.money.unknown')
      : stale
        ? ageText(t, reading, props.now, 'old')
        : t('field.money.balance');
  const ink = paid ? theme.colors.statusInk.success : stale ? theme.colors.statusInk.warning : theme.colors.text;

  return (
    <Card
      testID={props.testID ?? 'balance-card'}
      tone={tone}
      title={title}
      trailing={tone === 'warning' ? <Mark name="clock" colour={theme.colors.status.warning.fg} /> : undefined}
    >
      {reading ? (
        <View style={{ gap: theme.space[1] }}>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2], flexWrap: 'wrap' }}>
            <AppText variant="title" testID="balance-amount" style={{ color: ink }}>
              {formatMoney(reading.balance, reading.currency)}
            </AppText>
            <AppText variant="body" tone="muted">
              {t('field.money.owingAsOf', { day: formatDay(reading.asAt) })}
            </AppText>
          </View>
          {stale ? (
            <AppText variant="label" tone="muted">
              {t('field.money.readAtBar', { stamp: formatStamp(reading.asAt), minutes: MONEY_FRESH_MINUTES })}
            </AppText>
          ) : (
            <DotLine tone="success" testID="balance-fresh">
              {ageText(t, reading, props.now, 'read')}
            </DotLine>
          )}
        </View>
      ) : null}
      {reading ? <PaymentFacts reading={reading} /> : null}
      {failed ? <Notice tone="warning">{t('field.money.noSignal')}</Notice> : null}
      <Button
        variant={stale ? 'primary' : 'secondary'}
        size="sm"
        busy={checking}
        onPress={() => void check()}
        icon={<Mark name="refresh" colour={stale ? theme.colors.actionText : theme.colors.text} />}
        testID="check-now"
      >
        {t('field.money.checkNow')}
      </Button>
    </Card>
  );
}
