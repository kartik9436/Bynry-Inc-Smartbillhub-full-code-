/**
 * FF-27 Disconnect · stale money — a real-time check before an irreversible
 * act (US-FLD-025; E2E-11, E2E-12; R17, R18).
 *
 * The board: a 3-day-old balance in amber with *Check now*; the steps, the
 * next one warning that proceeding is recorded as unverified; and a red
 * *Disconnect anyway*. Tapping *Check now* (notes.txt): *"The amber 3-day-old
 * balance turns green, the amount drops to $0.00, and the red Disconnect
 * anyway becomes Close — customer paid."*
 *
 *   NEVER BLOCKED (R17). Stale or unknown, the button is live; it moves to the
 *     danger tier, and pressing it carries `money_unverified` — the figure and
 *     its as-at — to FF-34, whose close records it for the office (E2E-12:
 *     *"The office sees the word unverified on the order"*).
 *   NO CODE KNOWS WHAT A DISCONNECT IS (R18). The warning sits on the step
 *     whose template DECLARES a freshness: `detail.money_fresh_minutes` on the
 *     wo_item, copied from the job bundle (`sync/extras.ts`; it was dropped
 *     there until DEF-FLD-10642). A step without one never warns (TC-3) and
 *     never stops. Fresh is measured by THAT step's bar, not the global five.
 *   A FRESH CLEARED BALANCE STOPS THE STEP (FB-013, PO rulings 2026-10-28).
 *     *"Stop it, with 'Hand back to office'"* — the board's *Close — customer
 *     paid* is SUPERSEDED: the screen says *Balance cleared. Do not
 *     disconnect.* and offers *Close — payment received* (FF-34 with the
 *     figure the phone saw — the server refuses a paid close without it) and
 *     *Hand back to office* (FF-58). Stale or no signal: R17 unchanged, no
 *     paid close is offered.
 *   A DISCONNECT RAISED ON SITE ALSO STOPS (FB-028, PO 2026-10-31) while the
 *     notice period runs (*Notice period ends 5 Nov. Leave it on.*) or the
 *     account is protected (*Protected account. Leave it on.*), and each stop
 *     — the cleared balance included — is told to the office
 *     (`fieldGate.disconnectGate`). With no figure ever read those facts are
 *     unknown, so the step waits: *Check the balance with signal.*
 *   CONTRACTORS (R26) see the job and the steps, not the money; for them the
 *     check does not exist, so nothing is recorded as unverified.
 *   FB-023 (PO 2026-10-31): the money is read when the screen opens (F1); a
 *     POSTED payment counts as paid — owing $0.00 stops the step whether the
 *     bank has cleared it or not — and *Posted, not cleared* is shown and
 *     travels with the close (F2). The template's *Balance & payments* tick
 *     hides the balance card and payment facts and NEVER the stop: the step
 *     still reads the balance and still says *Balance cleared. Do not
 *     disconnect.* (F4, the coordinator's judgment in the same entry).
 */
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Kicker } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import { StatusChip } from '../../components/StatusChip';
import { fromJson } from '../../db/json';
import * as woItemQ from '../../db/queries/woItem';
import { fieldRaiseOf } from '../../db/queries/workOrder';
import { DispatchStateChip } from '../theDay/DispatchStateChip';
import { useTheme } from '../../theme';
import { BalanceCard } from './BalanceCard';
import { NotOnPhone, useHeader, type WaveScreenProps } from './common';
import { goTo, useNav, useJobId } from './fieldData';
import { addressLines, formatDay } from './format';
import { loadJob, seesMoney, showsOf } from './job';
import { disconnectGate, tellOnce } from './fieldGate';
import { isCleared, isFreshFor } from './money';
import { useMoney } from './useMoney';

/** A step that declares how fresh the money must be before it is done (R18). */
export function freshnessOf(detail: string | null): number | null {
  const d = fromJson<Record<string, unknown>>(detail);
  const m = d?.money_fresh_minutes;
  return typeof m === 'number' && m > 0 ? m : null;
}

export function DisconnectScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const job = loadJob(w, useJobId());
  const employee = seesMoney(w);
  // F4: the tick is NOT passed here — the stop needs the figure either way.
  const money = useMoney(w, job?.order.id ?? null, employee);
  useHeader({ title: job?.order.number ?? null });
  // FB-028 — a disconnect RAISED ON SITE adds two stops, and tells each.
  const raised = fieldRaiseOf(job?.order ?? null).raisedOnSite;
  const held = disconnectGate({ raisedOnSite: raised, employee, reading: money.reading });
  const heldReason = held.kind === 'stop' ? held.reason : null;
  useEffect(() => {
    if (!job || held.kind !== 'stop') return;
    tellOnce(w.money, job.order.id, {
      reason: held.reason,
      endsOn: held.reason === 'notice_open' ? held.endsOn : null,
      moneyAsAt: money.reading?.asAt ?? null,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [heldReason, job?.order.id]);
  if (!job) return <NotOnPhone />;

  const { order, premise, customer, asset } = job;
  const shows = showsOf(job);
  const steps = woItemQ.listForOrder(w.s, order.id, 'task');
  const next = steps.find((s) => s.state !== 'done') ?? null;
  const bar = next !== null ? freshnessOf(next.detail) : null;
  const gated = bar !== null;
  const now = w.clock.now();
  // R17 by the STEP's own bar (FB-013 judgment 2): older than it is warned.
  const fresh = bar !== null && isFreshFor(money.reading, bar, now);
  const unverified = employee && gated && !fresh;
  // FB-013 ruling (a): a FRESH read showing the balance cleared STOPS the step.
  // Only on a step that declares a check (R18), only for an employee (R26).
  const stopped = employee && gated && fresh && money.reading !== null && isCleared(money.reading.balance);
  // FB-028 — the office is told of the cleared stop too, on a raised job.
  if (stopped && raised) {
    tellOnce(w.money, order.id, { reason: 'balance_cleared', owing: money.reading?.balance ?? null, moneyAsAt: money.reading?.asAt ?? null });
  }
  const leaveOn = !stopped && held.kind !== 'none';
  const where = addressLines(premise);

  const proceed = () =>
    goTo(navigation, 'FF-34', {
      workOrderId: order.id,
      ...(unverified
        ? { moneyUnverified: { balance: money.reading?.balance ?? null, as_at: money.reading?.asAt ?? null } }
        : {}),
    });
  // Ruling (b): what the phone SAW travels with the close — the server re-reads
  // and stores both (`apps/work/money.paid_close_record`).
  const closePaid = () => {
    const r = money.reading;
    if (!r || !next) return;
    goTo(navigation, 'FF-34', {
      workOrderId: order.id,
      paymentReceived: {
        task_id: next.id,
        balance: r.balance,
        currency: r.currency,
        as_at: r.asAt,
        checked_at: w.clock.now().toISOString(),
        // F2 — posted or cleared, saved with the close as it was shown.
        latest_payment: r.latestPayment ? { amount: r.latestPayment.amount, at: r.latestPayment.at, state: r.latestPayment.state } : null,
      },
    });
  };

  return (
    <ScreenFrame
      footer={
        leaveOn ? (
          <Button variant="secondary" grow onPress={() => goTo(navigation, 'FF-58', { workOrderId: order.id })} testID="hand-back">
            {t('field.ff27.handBackToOffice')}
          </Button>
        ) : stopped ? (
          <>
            <Button variant="secondary" grow onPress={() => goTo(navigation, 'FF-58', { workOrderId: order.id })} testID="hand-back">
              {t('field.ff27.handBackToOffice')}
            </Button>
            <Button variant="primary" grow onPress={closePaid} testID="close-payment-received">
              {t('field.ff27.closePaymentReceived')}
            </Button>
          </>
        ) : (
          <Button variant={unverified ? 'danger' : 'primary'} grow onPress={proceed} testID="disconnect">
            {unverified ? t('field.ff27.disconnectAnyway') : t('field.ff27.disconnect')}
          </Button>
        )
      }
    >
      <View style={{ gap: theme.space[1] }}>
        {order.type ? <Kicker tone="brand">{order.type}</Kicker> : null}
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <DispatchStateChip state={order.dispatch_state} />
          {order.priority_code ? <StatusChip tone="danger">{order.priority_code}</StatusChip> : null}
        </View>
      </View>

      {employee && shows.balancePayments ? <BalanceCard money={money} now={w.clock.now()} /> : null}

      {stopped ? (
        <Notice tone="danger" icon={<Mark name="alert" colour={theme.colors.status.danger.fg} />} testID="balance-cleared">
          {t('field.ff27.balanceCleared')}
        </Notice>
      ) : null}
      {leaveOn ? (
        <Notice tone="danger" icon={<Mark name="alert" colour={theme.colors.status.danger.fg} />} testID="disconnect-held">
          {held.kind === 'stop' && held.reason === 'protected'
            ? t('field.ff27.protected')
            : held.kind === 'stop' && held.reason === 'notice_open'
              ? t('field.ff27.noticeOpen', { day: formatDay(`${held.endsOn}T12:00:00`) })
              : t('field.money.checkWithSignal')}
        </Notice>
      ) : null}
      {stopped && shows.balancePayments && money.reading?.latestPayment?.state === 'posted' ? (
        <AppText variant="label" tone="muted" testID="posted-not-cleared">
          {t('field.ff27.postedNotCleared')}
        </AppText>
      ) : null}

      <Card>
        <AppText variant="section">{customer?.name ?? ''}</AppText>
        <AppText variant="body">{where.line1}</AppText>
        <AppText variant="label" tone="muted">
          {[
            shows.accountSummary && customer?.account_number && t('field.ff25.account', { account: customer.account_number }),
            shows.assetCard && asset?.serial && t('field.ff26.meter', { serial: asset.serial }),
          ]
            .filter(Boolean)
            .join(' · ')}
        </AppText>
      </Card>

      <Card title={t('field.ff27.steps')} testID="steps-card">
        {steps.map((step, i) => {
          const done = step.state === 'done';
          if (step === next && unverified) {
            return (
              <Notice key={step.id} tone="warning" icon={<Mark name="warning" colour={theme.colors.status.warning.fg} />} testID="unverified-step">
                {t('field.ff27.unverifiedStep', { n: i + 1, step: step.label })}
              </Notice>
            );
          }
          return (
            <ListRow
              key={step.id}
              divider={i > 0}
              label={step.label}
              detail={done ? t('field.ff27.done') : undefined}
              leading={done ? <Mark name="check" colour={theme.colors.statusInk.success} /> : undefined}
            />
          );
        })}
      </Card>
    </ScreenFrame>
  );
}
