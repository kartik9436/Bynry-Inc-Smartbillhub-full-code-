/**
 * FF-10 Today — the technician's day (T-16; US-FLD-002, -015, -037, -043,
 * -045). Built from `wireframes/phone/FF-10-today.png` and the tablet's
 * `FF-10-T-today.png`.
 *
 * Top to bottom, as drawn: the frame's header (menu, *Today*, the bell);
 * *Mine · Nearby* (drawn on FF-11 and on the tablet's FF-10 T — the phone's
 * FF-10 board leaves it off, reported in `doors.ts`); the *waiting to send*
 * strip; the day tabs *Today · Tue · Wed* and, after them, *Later · All*
 * (FB-029, `LIST_TABS` below — not drawn on FF-10; ruled 2026-10-31);
 * *11 jobs · 6h 20m*, counting exactly the tab's own cards; the cards.
 *
 * ORDER: appointment window, never priority (R1) — `db/queries/day.ts`.
 *
 * SEARCH (R44: Today declares customer · address · work-order number, and a
 * declared control is wired before it ships): the box searches the handset's
 * own index, local first (R41), and says the answer is only what is on the
 * phone (R42). The design draws no search box on FF-10; requirement 37 asks
 * for one, so it sits above the cards. The declared FILTERS (status, service,
 * window) are NOT built and therefore not drawn — reported.
 *
 * THE CARD'S BUTTON (DEF-FLD-10607; PO 2026-10-26, *"A Resume — start"*):
 * *Start* on a job nothing is captured on (accepts it, opens Safety),
 * *Resume* on a started one (the next unfinished part), *Finish* when every
 * part is done (Debrief), none when closed — `theJob/nextPart.ts` `cardAct`,
 * the same rule as FF-15's *Continue*. The tablet's FF-10 T list is this
 * screen, so it reads the same.
 *
 * REFRESH (R43's pull-to-refresh): pulling the list re-reads the store and
 * runs `FieldData.sendNow` when the app wired one. The other three triggers
 * (foreground, push, fifteen minutes) belong to the sync service.
 */
import { useIsFocused, useNavigation } from '@react-navigation/native';
import { Fragment, useCallback, useLayoutEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, RefreshControl, ScrollView, View } from 'react-native';

import { AppText, Button, EmptyState, Field, Kicker, Notice, SegmentTabs, Sheet } from '../../components';
import {
  allCounts,
  dayBounds,
  dayCounts,
  type DayJob,
  jobsByIds,
  laterCounts,
  listAll,
  listDay,
  listLater,
  PAGE_SIZE,
} from '../../db/queries/day';
import { search } from '../../db/queries/searchIndex';
import { useTheme } from '../../theme';
import { DaySyncStrip } from './DaySyncStrip';
import { directionsUrl } from './directions';
import { addressForDirections, distanceText, duration, headingDate, jobDayKey, weekdayShort } from './format';
import { useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';
import { HeaderBell } from './HeaderBell';
import { DeclineSheet } from './DeclineSheet';
import { JobCard } from './JobCard';
import { ScreenBoundary } from './ScreenBoundary';
import { useTabletSelection } from '../../tablet/TabletFrame';
import { useJobPort } from '../theJob/JobPort';
import { loadJob } from '../theJob/jobModel';
import { type CardAct, cardAct } from '../theJob/nextPart';
import { useAcceptance } from './useAcceptance';

/** Today and the next two days, as the board's tabs draw them. */
export const DAY_TABS = 3;

/**
 * FB-029 (decision log 2026-10-31, PO C; `BR-FLD-00135`): after the three day
 * tabs, *Later* (every open job from 00:00 on day 3, no upper limit) and *All*
 * (every open job, overdue and undated included). Both group their cards
 * under date headings, page 50 at a time and read only the handset's store.
 */
export const LIST_TABS = ['later', 'all'] as const;
type ListTab = (typeof LIST_TABS)[number];

function isListTab(tab: string): tab is ListTab {
  return (LIST_TABS as readonly string[]).includes(tab);
}

/** A day's heading in Later and All — the kit's `Kicker`; *No date* for an undated job. */
function DateHeading(props: { dayKey: string | null; language: string; noDate: string }) {
  const theme = useTheme();
  return (
    <View style={{ paddingTop: theme.space[2] }}>
      <Kicker testID={`today-heading-${props.dayKey ?? 'none'}`}>
        {props.dayKey ? headingDate(props.dayKey, props.language) : props.noDate}
      </Kicker>
    </View>
  );
}

function TodayBody() {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const navigation = useNavigation();
  const { now, location, sendNow, storeVersion } = useFieldData();
  const s = useScoped();
  const [tab, setTab] = useState<string>('0');
  const [pages, setPages] = useState(1);
  const [query, setQuery] = useState('');
  const [more, setMore] = useState<DayJob | null>(null);
  const [declining, setDeclining] = useState<DayJob | null>(null);
  // DEF-FLD-10579: Start accepts a job not yet accepted; Decline before that.
  const acceptance = useAcceptance();
  const [refreshing, setRefreshing] = useState(false);
  const [tick, setTick] = useState(0);
  // Beside its detail on a tablet (FF-10 T), the open job is marked in the list.
  const picked = useTabletSelection();

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.screen.ff10'), headerRight: () => <HeaderBell /> });
  }, [navigation, t]);

  const today = now();
  const listTab = isListTab(tab) ? tab : null;
  const day = listTab ? 0 : Number(tab);
  const bounds = dayBounds(today, day);
  // Later starts where the day-after tab ends: local midnight starting day 3.
  const laterFrom = dayBounds(today, DAY_TABS).from;
  const searching = query.trim().length > 0;

  const jobs = useMemo(() => {
    if (!s) return [];
    if (searching) {
      const ids = search(s, query, { limit: PAGE_SIZE })
        .filter((h) => h.entity_kind === 'work_order')
        .map((h) => h.entity_id);
      return jobsByIds(s, ids);
    }
    if (listTab === 'later') return listLater(s, { from: laterFrom, limit: PAGE_SIZE * pages });
    if (listTab === 'all') return listAll(s, { limit: PAGE_SIZE * pages });
    return listDay(s, { ...bounds, today: day === 0, limit: PAGE_SIZE * pages });
    // `tick` re-reads after a refresh; `storeVersion` after ANY sync run wrote
    // the store (DEF-FLD-10359: a removal pulled by the runtime's own run).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s, searching, query, tab, pages, bounds.from, tick, storeVersion]);
  // DEF-FLD-10607: each card's first button — Start, Resume or Finish — read
  // from the job's own rows, the same rule as FF-15's Continue (`cardAct`).
  const port = useJobPort();
  const portVersion = port?.version ?? 0;
  const focused = useIsFocused();
  const acts = useMemo(() => {
    const out = new Map<string, CardAct>();
    for (const job of jobs) out.set(job.id, cardAct(port ? loadJob(port, job.id) : null));
    return out;
    // `portVersion` re-reads after a capture (a tick on FF-16 turns Start into
    // Resume); `focused`, whenever Today comes back into view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs, port, portVersion, focused]);
  // Each tab counts exactly the rows it lists, every page (DEF-FLD-10804).
  const counts = !s
    ? null
    : listTab === 'later'
      ? laterCounts(s, { from: laterFrom })
      : listTab === 'all'
        ? allCounts(s)
        : dayCounts(s, { ...bounds, today: day === 0 });
  const here = location.current();

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      if (sendNow) await sendNow();
    } catch {
      // The sync screen records a failed sync; the list re-reads regardless.
    } finally {
      setRefreshing(false);
      setTick((n) => n + 1);
    }
  }, [sendNow]);

  const tabs = [
    ...Array.from({ length: DAY_TABS }, (_, i) => {
      const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() + i);
      return { id: String(i), label: i === 0 ? t('field.today.today') : weekdayShort(d, i18n.language) };
    }),
    { id: 'later', label: t('field.today.later') },
    { id: 'all', label: t('field.today.all') },
  ];

  const emptyHelp = searching
    ? t('field.today.noMatchHelp')
    : listTab === 'later'
      ? t('field.today.noLaterHelp')
      : listTab === 'all'
        ? t('field.today.noAllHelp')
        : t('field.today.noJobsHelp');

  const navigateTo = (job: DayJob) => {
    const address = addressForDirections(job);
    return address ? () => void Linking.openURL(directionsUrl('google', address)) : null;
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="screen-FF-10">
      <SegmentTabs
        label={t('field.today.whose')}
        tabs={[
          { id: 'mine', label: t('field.today.mine'), testID: 'tab-mine' },
          { id: 'nearby', label: t('field.today.nearby'), testID: 'door-FF-11' },
        ]}
        active="mine"
        onSelect={(id) => {
          if (id === 'nearby') openScreen(navigation, 'FF-11');
        }}
      />
      <DaySyncStrip refreshKey={tick + (storeVersion ?? 0)} />
      <SegmentTabs
        label={t('field.today.whichDay')}
        tabs={tabs}
        active={tab}
        onSelect={(id) => {
          setTab(id);
          setPages(1);
        }}
        scrollable
        testID="day"
      />
      <ScrollView
        style={{ flex: 1 }}
        contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} />}
        keyboardShouldPersistTaps="handled"
        automaticallyAdjustKeyboardInsets
        testID="today-list"
      >
        {!s ? (
          <EmptyState
            title={t('field.today.notLoaded')}
            helper={t('field.today.notLoadedHelp')}
            ctaLabel={t('field.today.openSync')}
            onCta={() => openScreen(navigation, 'FF-50')}
            testID="today-not-loaded"
          />
        ) : (
          <>
            <Field label={t('field.today.find')} value={query} onChangeText={setQuery} autoCorrect={false} testID="today-search" />
            {searching ? (
              <Notice tone="info" testID="today-local-only">
                {t('field.search.localOnly')}
              </Notice>
            ) : counts ? (
              <AppText variant="label" tone="muted" testID="today-summary">
                {t('field.today.summary', { count: counts.left, time: duration(t, counts.plannedMinutes) })}
              </AppText>
            ) : null}
            {jobs.length === 0 ? (
              <EmptyState
                title={searching ? t('field.today.noMatch') : t('field.today.noJobs')}
                helper={emptyHelp}
                testID="today-empty"
              />
            ) : (
              jobs.map((job, i) => (
                <Fragment key={job.id}>
                  {listTab && !searching && (i === 0 || jobDayKey(jobs[i - 1] as DayJob) !== jobDayKey(job)) ? (
                    <DateHeading dayKey={jobDayKey(job)} language={i18n.language} noDate={t('field.today.noDate')} />
                  ) : null}
                  <JobCard
                    job={job}
                    distance={distanceText(t, here, job)}
                    onOpen={() => openScreen(navigation, 'FF-15', { jobId: job.id })}
                    act={acts.get(job.id)?.act ?? 'start'}
                    onStart={() => {
                      const next = acts.get(job.id) ?? cardAct(null);
                      if (next.to === null) return;
                      // Start accepts (MQ-026); Resume and Finish find it accepted and send nothing.
                      acceptance.start(job.id);
                      if (next.act === 'start') {
                        openScreen(navigation, 'FF-16', { jobId: job.id });
                        return;
                      }
                      port?.setOpenJobId(job.id);
                      openScreen(navigation, next.to, { workOrderId: job.id });
                    }}
                    acceptance={acceptance.of(job.id)}
                    onDecline={acceptance.available ? () => setDeclining(job) : undefined}
                    onNavigate={navigateTo(job)}
                    onMore={() => setMore(job)}
                    selected={picked.split && picked.selected === job.id}
                  />
                </Fragment>
              ))
            )}
            {!searching && jobs.length === PAGE_SIZE * pages ? (
              <Button onPress={() => setPages((p) => p + 1)} testID="today-more">
                {t('field.list.showMore')}
              </Button>
            ) : null}
          </>
        )}
      </ScrollView>
      <DeclineSheet
        job={declining}
        onClose={() => setDeclining(null)}
        onDecline={(id, answer) => {
          const done = acceptance.decline(id, answer);
          // Online, the office hears now; offline, it waits in the outbox.
          if (done && sendNow) void sendNow().catch(() => undefined);
          return done;
        }}
      />
      <Sheet
        visible={more != null}
        onClose={() => setMore(null)}
        title={more?.number ?? t('field.screen.ff15')}
        closeLabel={t('field.common.close')}
        testID="today-more-sheet"
      >
        <View style={{ gap: theme.touch.clear }}>
          <Button
            onPress={() => {
              const job = more;
              setMore(null);
              if (job) openScreen(navigation, 'FF-15', { jobId: job.id });
            }}
            testID="door-FF-15"
          >
            {t('field.today.openJob')}
          </Button>
          <Button
            onPress={() => {
              const job = more;
              setMore(null);
              if (job) openScreen(navigation, 'FF-14', { jobId: job.id });
            }}
            testID="today-open-stop"
          >
            {t('field.today.openStop')}
          </Button>
        </View>
      </Sheet>
    </View>
  );
}

export function TodayScreen() {
  return (
    <ScreenBoundary screen="FF-10">
      <TodayBody />
    </ScreenBoundary>
  );
}
