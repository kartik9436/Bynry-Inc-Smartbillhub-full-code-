/**
 * FF-26 Restoration — the payment cleared, how long is left to restore, who
 * and where, and the steps (US-FLD-012 TC-2; E2E-13).
 *
 *   PAYMENT CLEARED — the cleared payment and the balance now, read through
 *     the money port with its as-at stamp (R16 read only, R17 its age). An
 *     employee only (R26): a contractor sees the job without it.
 *   RESTORE WITHIN — the time left to the order's own deadline (`due_at`),
 *     and a bar of how much of the time since the payment cleared is gone.
 *     No figure here is invented: no deadline on the order, no countdown.
 *   TO DO — the order's tasks, each marked PHOTO when it needs one.
 *
 * *Start restoring* opens FF-17 Tasks (the board's link).
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { ScreenFrame } from '../../components/ScreenFrame';
import { StatusChip } from '../../components/StatusChip';
import * as woItemQ from '../../db/queries/woItem';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from './common';
import { goTo, useNav, useJobId } from './fieldData';
import { addressLines, formatClock, formatCountdown, formatDay, formatMoney, minutesBetween, sameDay } from './format';
import { loadJob, seesMoney, showsOf } from './job';
import { useMoney } from './useMoney';

export function RestorationScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const job = loadJob(w, useJobId());
  const employee = seesMoney(w);
  const money = useMoney(w, job?.order.id ?? null, employee);
  if (!job) return <NotOnPhone />;

  const now = w.clock.now();
  const { order, premise, customer, asset } = job;
  // FB-023 F2: the latest payment, labelled by its state — *Payment posted*
  // until the bank statement clears it (DEF-FLD-10792). F4: the tick hides it.
  const shows = showsOf(job);
  const cleared = shows.balancePayments ? (money.reading?.latestPayment ?? null) : null;
  const tasks = woItemQ.listForOrder(w.s, order.id, 'task');
  const left = order.due_at ? minutesBetween(now, order.due_at) : null;
  const start = cleared?.at ?? order.window_start;
  const total = start && order.due_at ? minutesBetween(start, order.due_at) : 0;
  const gone = total > 0 && left !== null ? Math.min(1, Math.max(0, 1 - left / total)) : 0;
  const where = addressLines(premise);

  return (
    <ScreenFrame
      footer={
        <Button variant="primary" grow onPress={() => goTo(navigation, 'FF-17', { workOrderId: order.id })} testID="door-FF-17">
          {t('field.ff26.start')}
        </Button>
      }
    >
      {employee && cleared && money.reading ? (
        <Card title={cleared.state === 'cleared' ? t('field.ff26.cleared') : t('field.ff26.posted')} testID="cleared-card">
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2] }}>
            <AppText variant="title" style={{ color: theme.colors.statusInk.success }} testID="cleared-amount">
              {formatMoney(cleared.amount, money.reading.currency)}
            </AppText>
            <AppText variant="body" tone="muted">
              {t('field.ff26.received')}
            </AppText>
          </View>
          <AppText variant="label" tone="muted">
            {[cleared.method, `${formatDay(cleared.at)} ${formatClock(cleared.at)}`, t('field.ff26.checkedAt', { time: formatClock(money.reading.asAt) })]
              .filter(Boolean)
              .join(' · ')}
          </AppText>
          <ListRow divider label={t('field.ff26.balanceNow')} value={formatMoney(money.reading.balance, money.reading.currency)} testID="balance-now" />
        </Card>
      ) : null}

      {left !== null && order.due_at ? (
        <Card testID="countdown-card">
          <View style={{ alignItems: 'center', gap: theme.space[1] }}>
            <AppText variant="micro" tone="muted" weight="heavy">
              {t('field.ff26.restoreWithin')}
            </AppText>
            <AppText variant="title" testID="countdown">
              {formatCountdown(left)}
            </AppText>
            <AppText variant="body" tone="muted">
              {sameDay(order.due_at, now)
                ? t('field.ff26.byToday', { time: formatClock(order.due_at) })
                : t('field.ff26.byDay', { day: formatDay(order.due_at), time: formatClock(order.due_at) })}
            </AppText>
          </View>
          <View
            accessible
            accessibilityRole="progressbar"
            accessibilityLabel={t('field.ff26.timeGone')}
            accessibilityValue={{ min: 0, max: 100, now: Math.round(gone * 100) }}
            style={{ height: theme.space[2], backgroundColor: theme.colors.surface }}
          >
            <View style={{ height: theme.space[2], width: `${Math.round(gone * 100)}%`, backgroundColor: theme.colors.statusInk.success }} />
          </View>
        </Card>
      ) : null}

      <Card>
        <AppText variant="section">{customer?.name ?? ''}</AppText>
        <AppText variant="body">{where.line1}</AppText>
        {shows.assetCard && asset?.serial ? (
          <AppText variant="label" tone="muted">
            {t('field.ff26.meter', { serial: asset.serial })}
          </AppText>
        ) : null}
      </Card>

      <Card title={t('field.ff26.toDo')} testID="todo-card">
        {tasks.map((task, i) => (
          <ListRow
            key={task.id}
            divider={i > 0}
            label={`${i + 1}  ${task.label}`}
            value={task.photo_required ? <StatusChip tone="danger">{t('field.ff26.photo')}</StatusChip> : undefined}
          />
        ))}
      </Card>
    </ScreenFrame>
  );
}
