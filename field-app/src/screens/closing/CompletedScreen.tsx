/**
 * FF-35 Completed — the jobs I closed, Today, This week or Earlier, each with
 * its outcome, whether the office has accepted it, and what I can do next
 * (US-FLD-024; R21, R22).
 *
 *   REOPEN is live until the office accepts the close and greyed after —
 *     then it is a correction and the office owns it (R22, TC-2).
 *   RAISE FOLLOW-ON opens FF-37 carrying this job's premise, account,
 *     customer and meter: a reconnect is a NEW order, never a reopen (R21),
 *     and the office approves it (R23).
 *
 * FB-030 (PO 2026-10-31, decision log *"a technician's history is the last 14
 * days, kept on the phone"*):
 *   - *Earlier* is days 8–14; nothing older is on the phone (R62's purge) and
 *     there is no server list beyond it.
 *   - A job closed on the web or another phone is here too: its card arrived
 *     completed (`sync/delta.ts`), and acceptance is read from the server's
 *     `accepted_at` (`job.acceptedAt`).
 *   - ON A PHONE THE CARD OPENS THE RECORD (`CompletedRecord`), pushed as its
 *     own screen — it used to open nothing. On a tablet the card PICKS the
 *     record beside the list, as FF-35 T draws it.
 *   - No speed figures: the card no longer carries the labour minutes.
 *
 * List controls (R44, the capability matrix): the drawn switch, newest first,
 * paged 50 at a time with *Show more*. The matrix's customer search and
 * outcome filter are not drawn on the board and are not built (reported, not
 * guessed).
 */
import { StackActions } from '@react-navigation/native';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { ChoiceChips } from '../../components/ChoiceChips';
import { DotLine } from '../../components/DotLine';
import { EmptyState } from '../../components/EmptyState';
import { ScreenFrame } from '../../components/ScreenFrame';
import { fromJson } from '../../db/json';
import * as customerQ from '../../db/queries/customer';
import * as premiseQ from '../../db/queries/premise';
import * as workOrderQ from '../../db/queries/workOrder';
import type { WorkOrderRow } from '../../db/queries/workOrder';
import * as closedQ from '../../db/queries/workOrderClosed';
import type { StatusTone } from '../../theme';
import { useTabletSelection } from '../../tablet/TabletFrame';
import { useTheme } from '../../theme';
import type { WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParam } from '../onSite/fieldData';
import { addressLines, formatClock, sameDay } from '../onSite/format';
import { acceptedAt } from '../onSite/job';
import { CompletedRecord } from './CompletedRecord';
import { OUTCOME_TONE } from './outcomeTone';

export { OUTCOME_TONE } from './outcomeTone';

export const PAGE = 50;
/** FB-030 — how far back the history reaches (R62's purge keeps no more). */
export const HISTORY_DAYS = 14;
const WEEKDAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'] as const;

export type Range = 'today' | 'week' | 'earlier';

function dayStart(now: Date, daysBack: number): string {
  const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  d.setDate(d.getDate() - daysBack);
  return d.toISOString();
}

/** Start of today, or of the six days before it, or of the 14-day window, on the handset's clock. */
export function sinceFor(range: Range, now: Date): string {
  if (range === 'week') return dayStart(now, 6);
  if (range === 'earlier') return dayStart(now, HISTORY_DAYS - 1);
  return dayStart(now, 0);
}

/** The window's end: *Earlier* stops where *This week* starts; the others run to now. */
export function beforeFor(range: Range, now: Date): string | null {
  return range === 'earlier' ? dayStart(now, 6) : null;
}

/** One closed job: a toned strip with the outcome and the time, then the job. */
function OutcomeCard(props: { order: WorkOrderRow; w: WaveScreenProps['w']; now: Date }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const { order, w, now } = props;
  const accepted = acceptedAt({ extra: fromJson<Record<string, unknown>>(order.extra) ?? {} });
  const tone: StatusTone = accepted ? 'neutral' : (OUTCOME_TONE[order.outcome ?? ''] ?? 'neutral');
  const pair = theme.colors.status[tone];
  const customer = order.customer_id ? customerQ.get(w.db, order.customer_id) : undefined;
  const premise = order.premise_id ? premiseQ.get(w.db, order.premise_id) : undefined;
  const closed = order.closed_at ?? '';
  const when = sameDay(closed, now) ? formatClock(closed) : t(`field.site.weekday.${WEEKDAYS[new Date(closed).getDay()]}`);
  const outcome = order.outcome ? t(`field.site.outcome.${order.outcome}`) : '';
  const strip = accepted ? t('field.ff35.accepted', { outcome }) : outcome;
  const where = addressLines(premise);
  // FF-35 T *Completed work beside its record*: beside the record a card PICKS
  // its job (the record shows it) and the picked one is ruled heavy. On a
  // phone the card OPENS the record as its own screen (FB-030) — it used to
  // open nothing, a dead tap (`completedRecord.test.tsx` guards it).
  const picked = useTabletSelection();
  const pickable = picked.inFrame && picked.split;
  const isPicked = pickable && picked.selected === order.id;
  const open = () => {
    if (pickable) picked.select(order.id);
    else navigation.dispatch(StackActions.push('FF-35', { workOrderId: order.id }));
  };

  return (
    <View
      testID={`completed-${order.number ?? order.id}`}
      style={{
        backgroundColor: theme.colors.card,
        borderColor: isPicked ? theme.colors.text : theme.colors.border,
        borderWidth: isPicked ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
      }}
    >
      <View
        style={{
          backgroundColor: pair.bg,
          paddingHorizontal: theme.space[4],
          paddingVertical: theme.space[2],
          flexDirection: 'row',
          justifyContent: 'space-between',
        }}
      >
        <AppText variant="micro" weight="heavy" style={{ color: pair.fg, textTransform: 'uppercase' }} testID="outcome-strip">
          {strip}
        </AppText>
        <AppText variant="micro" weight="heavy" style={{ color: pair.fg }}>
          {when}
        </AppText>
      </View>
      <View style={{ padding: theme.space[4], gap: theme.space[2] }}>
        <Pressable
          accessibilityRole="button"
          accessibilityState={pickable ? { selected: isPicked } : undefined}
          accessibilityLabel={[customer?.name, order.number, strip].filter(Boolean).join(', ')}
          accessibilityHint={pickable ? undefined : t('field.ff35.openRecord')}
          onPress={open}
          style={{ minHeight: theme.touch.control }}
          testID={`completed-${order.number ?? order.id}-pick`}
        >
          <AppText variant="section">{customer?.name ?? ''}</AppText>
          <AppText variant="body">{where.line1}</AppText>
          <AppText variant="label" tone="muted">
            {[order.number, order.type].filter(Boolean).join(' · ')}
          </AppText>
        </Pressable>
        {accepted ? (
          <DotLine tone="success" mark="check">
            {t('field.ff35.acceptedByOffice')}
          </DotLine>
        ) : (
          <DotLine tone="warning" mark="clock">
            {t('field.ff35.waitingForOffice')}
          </DotLine>
        )}
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <Button variant="primary" size="sm" grow onPress={() => goTo(navigation, 'FF-37', { carriedFrom: order.id })} testID={`raise-${order.number ?? order.id}`}>
            {t('field.ff35.raiseFollowOn')}
          </Button>
          <Button
            size="sm"
            disabled={accepted !== null}
            onPress={() => goTo(navigation, 'FF-36', { workOrderId: order.id })}
            testID={`reopen-${order.number ?? order.id}`}
          >
            {t('field.ff35.reopen')}
          </Button>
        </View>
      </View>
    </View>
  );
}

/** FB-030 — the record of one job, pushed over the list on a phone. */
function RecordScreen({ w, workOrderId }: WaveScreenProps & { workOrderId: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const row = workOrderQ.getMine(w.s, workOrderId);
  const accepted = row ? acceptedAt({ extra: fromJson<Record<string, unknown>>(row.extra) ?? {} }) : null;
  return (
    <ScreenFrame
      testID="completed-record-screen"
      footer={
        row ? (
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            <Button disabled={accepted !== null} onPress={() => goTo(navigation, 'FF-36', { workOrderId })} testID="completed-record-reopen">
              {t('field.ff35.reopen')}
            </Button>
            <Button grow variant="primary" onPress={() => goTo(navigation, 'FF-37', { carriedFrom: workOrderId })} testID="completed-record-raise">
              {t('field.ff35.raiseFollowOn')}
            </Button>
          </View>
        ) : undefined
      }
    >
      <CompletedRecord workOrderId={workOrderId} />
    </ScreenFrame>
  );
}

export function CompletedScreen(props: WaveScreenProps) {
  const opened = useParam('workOrderId');
  if (opened) return <RecordScreen w={props.w} workOrderId={opened} />;
  return <CompletedList {...props} />;
}

function CompletedList({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const [range, setRange] = useState<Range>('today');
  const [pages, setPages] = useState(1);
  const now = w.clock.now();
  const rows = closedQ.listClosedSince(w.s, { since: sinceFor(range, now), before: beforeFor(range, now), limit: PAGE * pages + 1 });
  const more = rows.length > PAGE * pages;
  const shown = rows.slice(0, PAGE * pages);

  return (
    <ScreenFrame
      header={
        <ChoiceChips
          fill
          label={t('field.ff35.range')}
          segments={[
            { id: 'today', label: t('field.ff35.today') },
            { id: 'week', label: t('field.ff35.week') },
            { id: 'earlier', label: t('field.ff35.earlier') },
          ]}
          active={range}
          onSelect={(id) => {
            setRange(id === 'week' || id === 'earlier' ? id : 'today');
            setPages(1);
          }}
          testID="range"
        />
      }
    >
      {shown.map((order) => (
        <OutcomeCard key={order.id} order={order} w={w} now={now} />
      ))}
      {shown.length === 0 ? <EmptyState title={t('field.ff35.none')} helper={t('field.ff35.noneHelper')} testID="completed-empty" /> : null}
      {more ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="show-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
    </ScreenFrame>
  );
}
