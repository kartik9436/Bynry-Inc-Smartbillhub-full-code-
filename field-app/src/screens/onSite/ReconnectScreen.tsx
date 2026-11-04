/**
 * FF-61 Before you reconnect — the arrears and the reconnect fee as TWO
 * questions, each with its own answer (US-FLD-075; R111, R17).
 *
 * A customer can clear the arrears and not pay the fee; one balance would
 * read $0.00 and say nothing (notes.txt). So the screen reads both through
 * the money port (N13 for the arrears, N14 for the fee — neither on the
 * branch yet) and shows each beside the other, with one age for both and
 * *Check now* (the same five minutes as a disconnect).
 *
 * NEVER BLOCKED (R17): *Reconnect anyway* is always live. With the fee
 * unpaid, or the figures stale, it carries what it knew to FF-34, whose close
 * records *reconnected with the fee outstanding* for billing to chase (TC-2).
 * *Leave it off* returns to the job.
 *
 * This order IS the reconnect: R21 makes a reconnect a new order, raised
 * from the disconnect (FF-35 → FF-37) — it is never a reopen.
 *
 * ⚠ **FB-028 (PO 2026-10-31) — A RECONNECT RAISED ON SITE IS GATED, AND THE
 * TWO SENTENCES ABOVE ARE NARROWED FOR IT.** R23 (*approved by the office*) is
 * superseded: the raised job is the technician's at once, and the step itself
 * is gated by the live balance against the template's *Reconnect limit*
 * (`fieldGate.reconnectGate`): at or below → *Reconnect*; above → *Still owes
 * $804.50. Leave it off.* and the office is told; not fresh → *Check the
 * balance with signal.* and no Reconnect. *Reconnect anyway* is NOT offered on
 * such a job. An office-requested reconnect (2026-10-29 C1) is unchanged.
 *
 * Contractors (R26) see the name; the money and its check are not shown.
 */
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { DotLine } from '../../components/DotLine';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { GroupLabel, ScreenFrame } from '../../components/ScreenFrame';
import { fieldRaiseOf } from '../../db/queries/workOrder';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from './common';
import { reconnectGate, tellOnce } from './fieldGate';
import { goTo, useNav, useJobId } from './fieldData';
import { addressLines, formatClock, formatDay, formatMoney, isZeroAmount, sameDay } from './format';
import { loadJob, seesMoney, showsOf } from './job';
import { ageText, useMoney } from './useMoney';

export function ReconnectScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const job = loadJob(w, useJobId());
  const employee = seesMoney(w);
  const money = useMoney(w, job?.order.id ?? null, employee);
  // FB-028 — a reconnect RAISED ON SITE is gated by its template's limit.
  const raise = fieldRaiseOf(job?.order ?? null);
  const gate = reconnectGate({
    raisedOnSite: raise.raisedOnSite,
    limit: raise.reconnectLimit,
    employee,
    reading: money.reading,
    stale: money.stale,
  });
  const stopOwing = gate.kind === 'stop' ? gate.owing : null;
  useEffect(() => {
    if (gate.kind !== 'stop' || !job) return;
    tellOnce(w.money, job.order.id, {
      reason: gate.reason,
      owing: gate.owing,
      limit: gate.limit,
      moneyAsAt: money.reading?.asAt ?? null,
    });
    // Once per stop: the figure that stopped it is what the office is told.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gate.kind, stopOwing, job?.order.id]);
  if (!job) return <NotOnPhone />;

  const now = w.clock.now();
  const { order, premise, customer } = job;
  // FB-023 F4 — the tick hides the money cards; what the phone knew still
  // travels with the close (C1: a reconnect is never refused for owing).
  const shows = showsOf(job);
  const showMoney = employee && shows.balancePayments;
  const r = money.reading;
  const fee = r?.reconnectFee ?? null;
  const arrearsClear = r !== null && isZeroAmount(r.balance);
  const feeOpen = fee !== null && !fee.paid;
  const doubt = showMoney && (money.stale || feeOpen || !arrearsClear || r === null);
  const s = theme.colors.status;
  // A tone drawn as ink on the card (DEF-FLD-10360): never `fg`, which is white in sunlight.
  const ink = theme.colors.statusInk;
  const when = (at: string) => (sameDay(at, now) ? t('field.ff61.today', { time: formatClock(at) }) : formatDay(at));

  const reconnect = () =>
    goTo(navigation, 'FF-34', {
      workOrderId: order.id,
      ...(employee && feeOpen ? { feeOutstanding: { amount: fee?.amount ?? null } } : {}),
      ...(employee && money.stale ? { moneyUnverified: { balance: r?.balance ?? null, as_at: r?.asAt ?? null } } : {}),
    });

  return (
    <ScreenFrame>
      <Card>
        <AppText variant="body" weight="heavy">
          {customer?.name ?? ''}
        </AppText>
        <AppText variant="label" tone="muted">
          {[shows.accountSummary ? customer?.account_number : null, addressLines(premise).line1].filter(Boolean).join(' · ')}
        </AppText>
      </Card>

      {showMoney ? (
        <>
          <GroupLabel>{t('field.ff61.twoThings')}</GroupLabel>
          <Card testID="arrears-card" style={arrearsClear ? { borderColor: s.success.rule } : undefined}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              <Mark name={arrearsClear ? 'check' : 'alert'} colour={arrearsClear ? ink.success : ink.warning} size="section" />
              <View style={{ flex: 1 }}>
                <AppText variant="body" weight="heavy">
                  {t('field.ff61.owed')}
                </AppText>
                {r?.arrearsBefore && r.latestPayment ? (
                  <AppText variant="label" tone="muted">
                    {t('field.ff61.wasPaid', { was: formatMoney(r.arrearsBefore, r.currency), when: when(r.latestPayment.at) })}
                  </AppText>
                ) : null}
              </View>
              <AppText variant="section" style={{ color: arrearsClear ? ink.success : ink.warning }} testID="arrears-amount">
                {r ? formatMoney(r.balance, r.currency) : '—'}
              </AppText>
            </View>
          </Card>

          <Card tone={feeOpen ? 'warning' : 'plain'} testID="fee-card">
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              <Mark name={fee?.paid ? 'check' : 'alert'} colour={fee?.paid ? ink.success : ink.warning} size="section" />
              <View style={{ flex: 1 }}>
                <AppText variant="body" weight="heavy" style={feeOpen ? { color: ink.warning } : undefined}>
                  {t('field.ff61.fee')}
                </AppText>
                {fee ? (
                  <AppText variant="label" tone="muted">
                    {fee.paid
                      ? t('field.ff61.feePaid', { day: formatDay(fee.chargedAt) })
                      : t('field.ff61.feeUnpaid', { day: formatDay(fee.chargedAt) })}
                  </AppText>
                ) : null}
              </View>
              <AppText variant="section" style={{ color: feeOpen ? ink.warning : theme.colors.text }} testID="fee-amount">
                {fee && r ? formatMoney(fee.amount, r.currency) : '—'}
              </AppText>
            </View>
            {feeOpen && arrearsClear ? (
              <AppText variant="body" weight="heavy" testID="fee-case">
                {t('field.ff61.clearedNotFee')}
              </AppText>
            ) : null}
          </Card>

          <Card testID="age-card">
            {r ? (
              <DotLine tone={money.stale ? 'warning' : 'success'} mark="clock" testID="both-age">
                {ageText(t, r, now, 'read')}
              </DotLine>
            ) : (
              <DotLine tone="warning" mark="clock">
                {t('field.money.unknown')}
              </DotLine>
            )}
            <Button size="sm" busy={money.checking} onPress={() => void money.check()} testID="check-now">
              {t('field.money.checkNow')}
            </Button>
            {money.failed ? (
              <AppText variant="label" tone="muted">
                {t('field.money.noSignal')}
              </AppText>
            ) : null}
          </Card>
        </>
      ) : null}

      {gate.kind === 'stop' || gate.kind === 'blocked' ? (
        <>
          <Notice tone="danger" icon={<Mark name="alert" colour={theme.colors.status.danger.fg} />} testID="reconnect-gated">
            {gate.kind === 'stop'
              ? t('field.ff61.stillOwes', { amount: formatMoney(gate.owing, r?.currency) })
              : gate.why === 'withheld'
                ? t('field.ff61.askOffice')
                : t('field.money.checkWithSignal')}
          </Notice>
          <Button grow onPress={() => goTo(navigation, 'FF-15', { workOrderId: order.id })} testID="leave-off">
            {t('field.ff61.leaveOff')}
          </Button>
        </>
      ) : gate.kind === 'pass' ? (
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <Button grow onPress={() => goTo(navigation, 'FF-15', { workOrderId: order.id })} testID="leave-off">
            {t('field.ff61.leaveOff')}
          </Button>
          <Button grow variant="primary" onPress={reconnect} testID="reconnect">
            {t('field.ff61.reconnect')}
          </Button>
        </View>
      ) : doubt ? (
        <Card tone="danger" title={t('field.ff61.notBlocked')} testID="not-blocked">
          <AppText variant="body">{t('field.ff61.feeChased')}</AppText>
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            <Button grow onPress={() => goTo(navigation, 'FF-15', { workOrderId: order.id })} testID="leave-off">
              {t('field.ff61.leaveOff')}
            </Button>
            <Button grow variant="danger" onPress={reconnect} testID="reconnect-anyway">
              {t('field.ff61.reconnectAnyway')}
            </Button>
          </View>
        </Card>
      ) : (
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <Button grow onPress={() => goTo(navigation, 'FF-15', { workOrderId: order.id })} testID="leave-off">
            {t('field.ff61.leaveOff')}
          </Button>
          <Button grow variant="primary" onPress={reconnect} testID="reconnect">
            {t('field.ff61.reconnect')}
          </Button>
        </View>
      )}
    </ScreenFrame>
  );
}
