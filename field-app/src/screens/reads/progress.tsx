/**
 * How the route stands — RW-22 Where you are, RW-23 Still to do, RW-24
 * Photos (EP-FLD-14, EP-FLD-12). Built from `wireframes/reads/RW-22…24*.png`.
 *
 * Every figure is counted from the readings themselves, never a stored tally
 * (Mobile data §11; US-FLD-040 TC-4). R120: what is left and what is next,
 * never how fast — so RW-22 shows no pace and no time-left estimate, and its
 * hourly bars are counts, not a rate.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, View } from 'react-native';

import { ActionBar, AppText, Button, Card, ChoiceChips, Kicker, ListRow, Notice, ProgressBar, Stat, StatRow } from '../../components';
import * as walkQ from '../../db/queries/readsWalk';
import { useDefaultSelection, usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { distanceText, metresBetween } from './figures';
import { PressCard, Spread } from './parts';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { resolveRoute, streetOf } from './records';
import { useReads } from './services';

function NoRoute() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <Notice tone="info">{t('field.reads.common.noRoute')}</Notice>
      <Button testID="door-RW-05" onPress={() => go('RW-05')}>
        {t('field.reads.common.theWalk')}
      </Button>
    </ScreenBody>
  );
}

function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** Readings per hour of the day they were taken, in the handset's own time. */
export function byHour(times: readonly string[]): Array<{ hour: number; n: number }> {
  const counts = new Map<number, number>();
  for (const iso of times) {
    const h = new Date(iso).getHours();
    counts.set(h, (counts.get(h) ?? 0) + 1);
  }
  const hours = [...counts.keys()].sort((a, b) => a - b);
  if (hours.length === 0) return [];
  const out: Array<{ hour: number; n: number }> = [];
  for (let h = hours[0] as number; h <= (hours[hours.length - 1] as number); h++) out.push({ hour: h, n: counts.get(h) ?? 0 });
  return out;
}

// ── RW-22 Where you are ─────────────────────────────────────────────────────

export function WhereYouAre() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const tally = useLive(() => (r ? walkQ.tally(s, r.id) : null), [r?.id]);
  const shots = useLive(() => (r ? walkQ.photoCounts(s, r.id) : null), [r?.id]);
  const hours = useLive(() => (r ? byHour(walkQ.captureTimes(s, r.id)) : []), [r?.id]);
  if (!r || !tally || !shots) return <NoRoute />;
  const most = Math.max(1, ...hours.map((h) => h.n));
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="door-RW-25" onPress={() => go('RW-25', { routeId: r.id })}>
            {t('field.reads.rw22.turnIn')}
          </Button>
          <Button variant="primary" grow testID="door-RW-05" onPress={() => go('RW-05', { routeId: r.id })}>
            {t('field.reads.rw22.keepGoing')}
          </Button>
        </ActionBar>
      }
    >
      <Card>
        <AppText variant="title" testID="done-of-total">
          {t('field.reads.rw22.doneOf', { done: tally.done, total: tally.total })}
        </AppText>
        <ProgressBar done={tally.done} problem={tally.could_not} total={tally.total} label={t('field.reads.rw22.doneOf', { done: tally.done, total: tally.total })} />
        {tally.started_at ? (
          <AppText variant="label" tone="muted">
            {t('field.reads.rw22.started', { time: hhmm(tally.started_at) })}
          </AppText>
        ) : null}
      </Card>
      <StatRow>
        <Stat tone="success" value={String(tally.read)} caption={t('field.reads.common.read')} testID="stat-read" />
        <Stat tone="warning" value={String(tally.could_not)} caption={t('field.reads.common.couldNot')} testID="stat-could-not" />
        <Stat value={String(tally.unread)} caption={t('field.reads.common.left')} testID="stat-left" />
      </StatRow>
      <Card tone={tally.flagged ? 'warning' : 'plain'}>
        <ListRow
          label={t('field.reads.rw22.flagged', { n: tally.flagged })}
          detail={t('field.reads.rw22.flaggedDetail')}
          onPress={() => go('RW-23', { routeId: r.id, tab: 'flagged' })}
          testID="door-RW-23"
        />
      </Card>
      <Card>
        <ListRow
          label={t('field.reads.rw22.photos', { n: shots.total })}
          detail={t('field.reads.rw22.photosDetail', { sent: shots.sent, waiting: shots.waiting })}
          onPress={() => go('RW-24', { routeId: r.id })}
          testID="door-RW-24"
        />
      </Card>
      {hours.length ? (
        <Card title={t('field.reads.rw22.byHour')}>
          <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: theme.space[2], height: theme.touch.primary * 2 }} testID="by-hour">
            {hours.map((h) => (
              <View key={h.hour} style={{ flex: 1, alignItems: 'center', gap: theme.space[1] }} accessible accessibilityLabel={`${h.hour}: ${h.n}`}>
                <View style={{ alignSelf: 'stretch', flexGrow: 0, height: `${Math.round((h.n / most) * 80)}%`, backgroundColor: theme.colors.status.success.rule }} />
                <AppText variant="micro" tone="muted">
                  {String(h.hour)}
                </AppText>
              </View>
            ))}
          </View>
        </Card>
      ) : null}
    </ScreenBody>
  );
}

// ── RW-23 Still to do ───────────────────────────────────────────────────────

type Tab = 'not_read' | 'came_back' | 'flagged';

export function StillToDo() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, here } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const [tab, setTab] = useState<Tab>((params.tab as Tab) ?? 'not_read');
  const counts = useLive(
    () => (r ? { not_read: walkQ.stopCount(s, r.id, 'not_read'), came_back: walkQ.stopCount(s, r.id, 'came_back'), flagged: walkQ.stopCount(s, r.id, 'flagged') } : null),
    [r?.id],
  );
  const list = useLive(
    () => (r ? walkQ.stops(s, r.id, { order: here ? 'nearest' : 'walk', from: here, filter: tab }) : []),
    [r?.id, tab, here?.lat, here?.lng],
  );
  // RW-23 T: beside the stop, the nearest is picked until another is, and a
  // card's door to RW-06 picks it (`SelectOnOpen` in the layout).
  const pick = usePick();
  useDefaultSelection(list[0]?.id ?? null);
  if (!r || !counts) return <NoRoute />;
  const first = list[0] ?? null;
  const away = (st: walkQ.StopCard) =>
    here && st.lat !== null && st.lng !== null ? distanceText(metresBetween(here, { lat: st.lat, lng: st.lng })) : '';
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="door-RW-04" onPress={() => go('RW-04', { routeId: r.id })}>
            {t('field.reads.rw23.onMap')}
          </Button>
          <Button variant="primary" grow disabled={!first} testID="door-RW-06" onPress={() => first && go('RW-06', { stopId: first.id })}>
            {first ? t('field.reads.rw23.nearest', { address: streetOf(first) }) : t('field.reads.rw05.openNone')}
          </Button>
        </ActionBar>
      }
    >
      <ChoiceChips
        label={t('field.screen.rw23')}
        active={tab}
        onSelect={(id) => setTab(id as Tab)}
        segments={[
          { id: 'not_read', label: t('field.reads.rw23.notRead', { n: counts.not_read }) },
          { id: 'came_back', label: t('field.reads.rw23.cameBack', { n: counts.came_back }) },
          { id: 'flagged', label: t('field.reads.rw23.flagged', { n: counts.flagged }) },
        ]}
        testID="still-tabs"
      />
      {list.length === 0 ? <Notice tone="success">{t('field.reads.rw23.none')}</Notice> : null}
      {list.map((st, i) => {
        const warn = st.could_not > 0;
        const line = warn
          ? [st.last_reason, st.last_captured_at ? hhmm(st.last_captured_at) : null].filter(Boolean).join(' · ')
          : t('field.reads.rw23.notReached', { n: st.unread });
        return (
          <PressCard
            key={st.id}
            label={streetOf(st)}
            emphasis={pick.isPicked(st.id) ? 'strong' : warn ? 'warning' : 'none'}
            onPress={() => go('RW-06', { stopId: st.id })}
            testID={`todo-${i}`}
          >
            <Spread>
              <View style={{ flexShrink: 1 }}>
                <AppText variant="body" weight="heavy">
                  {streetOf(st)}
                </AppText>
                <AppText variant="label" style={warn ? { color: theme.colors.statusInk.warning } : undefined} tone={warn ? undefined : 'muted'}>
                  {line}
                </AppText>
              </View>
              <AppText variant="body" weight="heavy">
                {away(st)}
              </AppText>
            </Spread>
          </PressCard>
        );
      })}
      <Notice tone="info">{here ? t('field.reads.rw23.byDistance') : t('field.reads.rw23.byWalk')}</Notice>
      <Button testID="door-RW-22" onPress={() => go('RW-22', { routeId: r.id })}>
        {t('field.screen.rw22')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-24 Photos ────────────────────────────────────────────────────────────

export function Photos() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const list = useLive(() => (r ? walkQ.photos(s, r.id) : []), [r?.id]);
  const counts = useLive(() => (r ? walkQ.photoCounts(s, r.id) : null), [r?.id]);
  if (!r || !counts) return <NoRoute />;
  const groups = new Map<string, walkQ.RoutePhoto[]>();
  for (const p of list) {
    const key = p.address_line ?? t('field.reads.rw24.elsewhere');
    groups.set(key, [...(groups.get(key) ?? []), p]);
  }
  const mb = (counts.bytes_waiting / (1024 * 1024)).toFixed(1);
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button variant="primary" grow testID="door-RW-22" onPress={() => go('RW-22', { routeId: r.id })}>
            {t('field.reads.rw24.back')}
          </Button>
        </ActionBar>
      }
    >
      <Spread>
        <AppText variant="label" testID="photo-line">
          {t('field.reads.rw24.line', { sent: counts.sent, waiting: counts.waiting })}
        </AppText>
        <AppText variant="label" tone="muted">
          {t('field.reads.rw24.mb', { mb })}
        </AppText>
      </Spread>
      {list.length === 0 ? <Notice tone="info">{t('field.reads.rw24.none')}</Notice> : null}
      {[...groups.entries()].map(([address, ps]) => (
        <View key={address} style={{ gap: theme.space[2] }}>
          <Kicker>{t('field.reads.rw24.group', { address, n: ps.length })}</Kicker>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[2] }}>
            {ps.map((p) => (
              <View
                key={p.id}
                accessible
                accessibilityLabel={`${hhmm(p.captured_at)} · ${p.state === 'uploaded' ? t('field.reads.rw24.sent') : t('field.reads.rw24.waiting')}`}
                testID={`photo-${p.id}-${p.state === 'uploaded' ? 'sent' : 'waiting'}`}
                style={{ width: theme.touch.primary * 2, height: theme.touch.primary * 2, backgroundColor: theme.colors.toastFill }}
              >
                <Image source={{ uri: p.local_path }} style={{ flex: 1 }} accessibilityIgnoresInvertColors />
                <View style={{ position: 'absolute', bottom: 0, left: 0, right: 0, padding: theme.space[1], backgroundColor: theme.colors.toastFill }}>
                  <AppText variant="micro" style={{ color: theme.colors.toastText }}>
                    {`${hhmm(p.captured_at)} · ${p.state === 'uploaded' ? '✓' : '…'}`}
                  </AppText>
                </View>
              </View>
            ))}
          </View>
        </View>
      ))}
      <Card>
        <AppText variant="body">{t('field.reads.rw24.cameraOnly')}</AppText>
      </Card>
    </ScreenBody>
  );
}
