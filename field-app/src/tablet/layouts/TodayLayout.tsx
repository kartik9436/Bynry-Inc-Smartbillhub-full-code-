/**
 * FF-10 T *Today beside the job* (T-28; image `tablet/FF-10-T-today.png`).
 *
 *   LIST   — the phone's Today, whole: *Mine · Nearby*, the *waiting to
 *            send* strip, the day tabs, the search and the cards, under its
 *            own *Today* header. A card's body, which opens the job on a
 *            phone, picks it here (`SelectOnOpen`), so the list never leaves
 *            the screen; *Start*, *Navigate* and *⋮* do what they always do.
 *   DETAIL — the picked job (the first of the day until one is picked, as
 *            the board draws it): its number and state, the two clocks, the
 *            customer and the meter, how far each part of the template is,
 *            and *Notes* · *Continue — step 4 of 8* · *Open the stop*.
 *            *Continue* goes to the job's NEXT UNFINISHED PART — the same
 *            `nextPart`/`nextPartLabel` as the phone's FF-15, so safety →
 *            tasks → materials → readings → *Finish — debrief* (FF-32)
 *            (DEF-FLD-10590; it copied the old safety-or-tasks logic and
 *            read *"step n of n"* once every task was done).
 *
 * The detail reads the job through the job services (`theJob/jobModel`), the
 * same counts FF-15 shows, so the two can never disagree. ⚠ Its four acts
 * are doors the PHONE board does not draw from FF-10 (to FF-30, FF-17, FF-16
 * and FF-14 — `navigation/doors.ts` has FF-10 → FF-15, FF-16 only); they are
 * the tablet board's, and are reported for the door table rather than added
 * to it here. Their test ids are `pane-<id>`, not `door-<id>`, for that
 * reason.
 */
import { type NavigationProp, type ParamListBase, useNavigation } from '@react-navigation/native';
import { type TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, EmptyState, ListRow, Stat, StatRow, StatusChip } from '../../components';
import { dayBounds, listDay } from '../../db/queries/day';
import { type ScreenId } from '../../navigation/screens';
import { useFieldData, useScoped } from '../../screens/theDay/fieldData';
import { openScreen } from '../../screens/theDay/go';
import { statusLook } from '../../screens/theDay/jobStatus';
import { TodayScreen } from '../../screens/theDay/TodayScreen';
import { shortDuration } from '../../screens/theJob/format';
import { useJobPort } from '../../screens/theJob/JobPort';
import { type JobView } from '../../screens/theJob/jobModel';
import { nextPart, nextPartLabel } from '../../screens/theJob/nextPart';
import { useTheme } from '../../theme';
import { SelectOnOpen, useDefaultSelection, useSelectedOr } from '../selection';
import { HeadedPane, PaneScreen, useJobView } from './parts';

export function TodayList() {
  const { t } = useTranslation();
  return (
    <HeadedPane title={t('field.screen.ff10')} testID="today-list-pane">
      <SelectOnOpen opens="FF-15" param="jobId">
        <TodayScreen />
      </SelectOnOpen>
    </HeadedPane>
  );
}

/** "3 of 8", or the part's own word when it says more (Materials: "1 short"). */
function partValue(t: TFunction, done: number, total: number): string {
  return total > 0 ? t('field.job.nOfM', { done, total }) : '';
}

function JobSummary({ view }: { view: JobView }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const port = useJobPort();
  const order = view.order;
  const units = { h: t('field.job.unit.h'), m: t('field.job.unit.m') };
  const look = statusLook(order.dispatch_state);
  const next = nextPart(view);
  const total = view.tasks.total;
  const open = (id: ScreenId, params: object = { workOrderId: order.id }) => {
    port?.setOpenJobId(order.id);
    openScreen(navigation, id, params);
  };
  const premise = view.premise;
  const asset = view.asset;
  const readings = [
    partValue(t, view.readings.taken, view.readings.total),
    view.readings.flagged > 0 ? t('field.tablet.flagged', { count: view.readings.flagged }) : null,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <PaneScreen
      title={order.number ?? order.id}
      trailing={look.labelKey ? <StatusChip tone={look.tone}>{t(look.labelKey)}</StatusChip> : undefined}
      testID="today-detail"
      footer={
        <View style={{ flex: 1, gap: theme.space[2] }}>
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            <Button onPress={() => open('FF-30')} testID="pane-FF-30">
              {t('field.ff15.notes')}
            </Button>
            <Button
              grow
              variant="primary"
              onPress={() => {
                if (next.to !== null) open(next.to);
              }}
              disabled={next.to === null}
              testID="today-detail-continue"
            >
              {nextPartLabel(next, t)}
            </Button>
          </View>
          <Button onPress={() => open('FF-14', { jobId: order.id })} testID="pane-FF-14">
            {t('field.today.openStop')}
          </Button>
        </View>
      }
    >
      <StatRow testID="today-detail-clocks">
        <Stat value={shortDuration(view.travel.minutes, units)} caption={t('field.tablet.travel')} />
        <Stat value={shortDuration(view.labour.minutes, units)} caption={t('field.tablet.onSite')} tone="success" />
      </StatRow>
      <Card testID="today-detail-customer">
        <AppText variant="section">{view.customer?.name ?? premise?.address_line ?? ''}</AppText>
        {premise?.address_line ? <AppText variant="body">{premise.address_line}</AppText> : null}
        {asset ? (
          <AppText variant="label" tone="muted">
            {[asset.serial ?? asset.badge, asset.model, asset.size].filter(Boolean).join(' · ')}
          </AppText>
        ) : null}
      </Card>
      <Card testID="today-detail-parts">
        <ListRow label={t('field.ff15.safety')} value={partValue(t, view.safety.done, view.safety.total)} onPress={() => open('FF-16')} testID="pane-FF-16" />
        <ListRow divider label={t('field.ff15.tasks')} value={partValue(t, view.tasks.done, total)} onPress={() => open('FF-17')} testID="pane-FF-17" />
        <ListRow
          divider
          label={t('field.ff15.materials')}
          value={view.materials.short > 0 ? t('field.tablet.short', { count: view.materials.short }) : partValue(t, view.materials.satisfied, view.materials.planned.length)}
          onPress={() => open('FF-23')}
          testID="pane-FF-23"
        />
        <ListRow divider label={t('field.ff15.readings')} value={readings} onPress={() => open('FF-20')} testID="pane-FF-20" />
      </Card>
    </PaneScreen>
  );
}

export function TodayDetail() {
  const { t } = useTranslation();
  const { now } = useFieldData();
  const s = useScoped();
  const first = s ? (listDay(s, { ...dayBounds(now(), 0), today: true, limit: 1 })[0]?.id ?? null) : null;
  useDefaultSelection(first);
  const id = useSelectedOr('jobId') ?? first;
  const view = useJobView(id);
  if (!view) {
    return (
      <PaneScreen title={t('field.screen.ff15')} testID="today-detail">
        <EmptyState title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID="today-detail-none" />
      </PaneScreen>
    );
  }
  return <JobSummary view={view} />;
}
