/**
 * FF-63 Home — both modules at a glance (T-16; US-FLD-078; AD-22). Built
 * from `wireframes/phone/FF-63-home.png` and `tablet/FF-63-T-home.png`.
 *
 * As drawn: the header (menu, the technician's name, the bell), the date
 * line, the *waiting to send* strip, the JOBS tile (*8 left today · 3 done ·
 * 1 on hold*, NEXT *1400 Elm Street · Unit A*, *08:00–12:00*), the READS tile
 * (*15 meters left · 129 read · 7 could not be*, NEAREST STOP *1318 Maple
 * Street · 3 meters*, *route WLK-07*), *Scan a meter · Raise work*, and the
 * hours row (*4h 52m today · Travel 48m · on site 3h 04m*).
 *
 * R120 — what is left and what is next, NEVER how fast: no reads per hour,
 * no average job time, no ranking. The board's footnote explaining that
 * (*"Not how fast you are going — this screen does not score anybody"*) is
 * RATIONALE and is zero words on screen (B14 rule 33); it lives here.
 *
 * Every figure is COUNTED from the handset's rows (`db/queries/day.ts`),
 * never a stored tally. *Nearest stop* needs a position: without one the
 * tile says *Next stop* and takes the next in walk order — it never claims a
 * nearness it did not measure. *On shift until 16:00* needs the shift, which
 * is the Shifts wave's (FF-46) and is not on the handset yet, so the date
 * line carries the date alone.
 */
import { useIsFocused, useNavigation } from '@react-navigation/native';
import { useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, EmptyState, Glyph, ListRow, Page } from '../../components';
import {
  dayBounds,
  dayCounts,
  DISPATCH,
  hoursToday,
  listDay,
  PAGE_SIZE,
  readCounts,
  stopsToRead,
  type StopToRead,
} from '../../db/queries/day';
import { useOptionalSession } from '../../session/SessionProvider';
import { useTheme } from '../../theme';
import { DaySyncStrip } from './DaySyncStrip';
import { distanceText, duration, longDate, milesBetween, windowText } from './format';
import { type Position, useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';
import { HeaderBell } from './HeaderBell';
import { HomeTile } from './HomeTile';
import { COLUMN_GAP, useSideBySide } from '../../tablet/columns';
import { ScreenBoundary } from './ScreenBoundary';

/** The stop to show: the nearest when the handset knows where it is, else the next in walk order. */
export function pickStop(stops: readonly StopToRead[], here: Position | null): { stop: StopToRead; nearest: boolean } | null {
  if (stops.length === 0) return null;
  if (!here) return { stop: stops[0] as StopToRead, nearest: false };
  let best: StopToRead | null = null;
  let bestMi = Infinity;
  for (const st of stops) {
    if (st.lat == null || st.lng == null) continue;
    const d = milesBetween(here, { lat: st.lat, lng: st.lng });
    if (d < bestMi) {
      bestMi = d;
      best = st;
    }
  }
  return best ? { stop: best, nearest: true } : { stop: stops[0] as StopToRead, nearest: false };
}

function HomeBody() {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const navigation = useNavigation();
  const session = useOptionalSession();
  const { now, location } = useFieldData();
  const s = useScoped();
  const name = session?.snapshot.active?.displayName ?? '';
  // Home stays mounted under the screens it opens, so coming back to it must
  // re-read the counts: a raise sent from FF-37 left *waiting to send* at its
  // old figure until something else re-rendered Home (DEF-FLD-10603).
  useIsFocused();

  useLayoutEffect(() => {
    navigation.setOptions({ title: name || t('field.screen.ff63'), headerRight: () => <HeaderBell /> });
  }, [navigation, name, t]);

  const sideBySide = useSideBySide();
  const today = now();
  const bounds = dayBounds(today, 0);
  const here = location.current();

  if (!s) {
    return (
      <Page testID="screen-FF-63">
        <EmptyState
          title={t('field.today.notLoaded')}
          helper={t('field.today.notLoadedHelp')}
          ctaLabel={t('field.today.openSync')}
          onCta={() => openScreen(navigation, 'FF-50')}
          testID="home-not-loaded"
        />
      </Page>
    );
  }

  const jobs = dayCounts(s, { ...bounds, today: true });
  const next = listDay(s, { ...bounds, today: true, limit: PAGE_SIZE }).find((j) => j.dispatchState !== DISPATCH.onHold) ?? null;
  const reads = readCounts(s);
  const picked = pickStop(stopsToRead(s), here);
  const nextJobLine = next ? (next.addressLine ?? next.customerName ?? next.number) : null;
  const nextJobDetail = next ? [windowText(next.windowStart, next.windowEnd), distanceText(t, here, next)].filter(Boolean).join(' · ') : null;
  const stop = picked?.stop ?? null;
  const stopDistance = picked?.nearest && stop ? distanceText(t, here, stop) : null;

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="screen-FF-63">
      <View style={{ paddingHorizontal: theme.space[4], paddingVertical: theme.space[2], backgroundColor: theme.colors.card }}>
        <AppText variant="label" tone="muted" testID="home-date">
          {longDate(today, i18n.language)}
        </AppText>
      </View>
      <DaySyncStrip />
      <Page>
        {/* FF-63 T: on a tablet's wide pane the two tiles sit side by side —
            only where the PANE holds two columns of 260 (R121, R122). */}
        {sideBySide ? (
          <View style={{ flexDirection: 'row', gap: COLUMN_GAP }} testID="home-tiles-row">
            <View style={{ flex: 1 }}>
                <HomeTile
                  testID="home-jobs"
                  emphasis
                  title={t('field.home.jobs')}
                  glyph="calendar"
                  openLabel={t('field.home.open')}
                  onOpen={() => openScreen(navigation, 'FF-10')}
                  openTestID="door-FF-10"
                  figures={[
                    { value: String(jobs.left), label: t('field.home.leftToday'), testID: 'home-jobs-left' },
                    { value: String(jobs.done), label: t('field.home.done'), tone: 'success', testID: 'home-jobs-done' },
                    { value: String(jobs.onHold), label: t('field.home.onHold'), tone: 'warning', testID: 'home-jobs-hold' },
                  ]}
                  nextKicker={t('field.home.next')}
                  nextLine={nextJobLine}
                  nextDetail={nextJobDetail}
                  nothingNext={t('field.home.nothingNext')}
                />
            </View>
            <View style={{ flex: 1 }}>
                <HomeTile
                  testID="home-reads"
                  title={t('field.home.reads')}
                  glyph="pin"
                  openLabel={t('field.home.open')}
                  onOpen={() => openScreen(navigation, 'RW-01')}
                  openTestID="door-RW-01"
                  figures={[
                    { value: String(reads.left), label: t('field.home.metersLeft'), testID: 'home-reads-left' },
                    { value: String(reads.read), label: t('field.home.read'), tone: 'success', testID: 'home-reads-read' },
                    { value: String(reads.couldNot), label: t('field.home.couldNot'), tone: 'warning', testID: 'home-reads-could-not' },
                  ]}
                  nextKicker={picked?.nearest ? t('field.home.nearestStop') : t('field.home.nextStop')}
                  nextLine={stop ? t('field.home.stopLine', { address: stop.addressLine ?? '', count: stop.meters }) : null}
                  nextDetail={stop ? [stopDistance, stop.routeCode ? t('field.home.route', { code: stop.routeCode }) : null].filter(Boolean).join(' · ') : null}
                  nothingNext={t('field.home.nothingToRead')}
                />
            </View>
          </View>
        ) : (
          <>
            <HomeTile
              testID="home-jobs"
              emphasis
              title={t('field.home.jobs')}
              glyph="calendar"
              openLabel={t('field.home.open')}
              onOpen={() => openScreen(navigation, 'FF-10')}
              openTestID="door-FF-10"
              figures={[
                { value: String(jobs.left), label: t('field.home.leftToday'), testID: 'home-jobs-left' },
                { value: String(jobs.done), label: t('field.home.done'), tone: 'success', testID: 'home-jobs-done' },
                { value: String(jobs.onHold), label: t('field.home.onHold'), tone: 'warning', testID: 'home-jobs-hold' },
              ]}
              nextKicker={t('field.home.next')}
              nextLine={nextJobLine}
              nextDetail={nextJobDetail}
              nothingNext={t('field.home.nothingNext')}
            />
            <HomeTile
              testID="home-reads"
              title={t('field.home.reads')}
              glyph="pin"
              openLabel={t('field.home.open')}
              onOpen={() => openScreen(navigation, 'RW-01')}
              openTestID="door-RW-01"
              figures={[
                { value: String(reads.left), label: t('field.home.metersLeft'), testID: 'home-reads-left' },
                { value: String(reads.read), label: t('field.home.read'), tone: 'success', testID: 'home-reads-read' },
                { value: String(reads.couldNot), label: t('field.home.couldNot'), tone: 'warning', testID: 'home-reads-could-not' },
              ]}
              nextKicker={picked?.nearest ? t('field.home.nearestStop') : t('field.home.nextStop')}
              nextLine={stop ? t('field.home.stopLine', { address: stop.addressLine ?? '', count: stop.meters }) : null}
              nextDetail={stop ? [stopDistance, stop.routeCode ? t('field.home.route', { code: stop.routeCode }) : null].filter(Boolean).join(' · ') : null}
              nothingNext={t('field.home.nothingToRead')}
            />
          </>
        )}
        <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          <Button grow icon={<Glyph name="scan" />} onPress={() => openScreen(navigation, 'FF-38')} testID="door-FF-38">
            {t('field.home.scan')}
          </Button>
          <Button grow icon={<Glyph name="more" />} onPress={() => openScreen(navigation, 'FF-37', { returnTo: 'FF-63' })} testID="door-FF-37">
            {t('field.home.raise')}
          </Button>
        </View>
        <HoursRow />
      </Page>
    </View>
  );
}

/** *4h 52m today · Travel 48m · on site 3h 04m · admin 1h* → Timesheet (FF-47). */
function HoursRow() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { now } = useFieldData();
  const s = useScoped();
  if (!s) return null;
  const today = now();
  const h = hoursToday(s, dayBounds(today, 0), today);
  const detail = [
    t('field.home.travel', { time: duration(t, h.byKind.travel) }),
    t('field.home.onSite', { time: duration(t, h.byKind.labour) }),
    h.byKind.admin > 0 ? t('field.home.admin', { time: duration(t, h.byKind.admin) }) : null,
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <View
      style={{
        backgroundColor: theme.colors.card,
        borderColor: theme.colors.border,
        borderWidth: theme.borderWidth.card,
        borderRadius: theme.radius.lg,
        paddingHorizontal: theme.space[4],
      }}
    >
      <ListRow
        leading={<Glyph name="pending" colour={theme.colors.textMuted} />}
        label={t('field.home.hoursToday', { time: duration(t, h.totalMinutes) })}
        detail={detail}
        onPress={() => openScreen(navigation, 'FF-47')}
        testID="door-FF-47"
      />
    </View>
  );
}

export function HomeScreen() {
  return (
    <ScreenBoundary screen="FF-63">
      <HomeBody />
    </ScreenBoundary>
  );
}
