/**
 * Getting a route and walking it — RW-01 My routes, RW-02 Route summary,
 * RW-03 Download, RW-04 Route map, RW-05 The walk (EP-FLD-10, EP-FLD-11).
 * Built from `wireframes/reads/RW-01…05*.png` and their tablet boards.
 *
 * R73: Reads is a mode of the same app — the sync line on RW-01 is the same
 * outbox as jobs. R74: the walk lists ADDRESSES. R75: nearest first by
 * default, the office's walk order one tap away. R76: nearest needs no
 * signal — each stop's point came down with the route; only the reader's own
 * position is live. R77: any order is fine and never refused; the order
 * actually walked is the readings' own capture times.
 */
import type { TFunction } from 'i18next';
import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import {
  ActionBar,
  AppText,
  Button,
  Card,
  ChoiceChips,
  IconButton,
  Kicker,
  ListRow,
  Notice,
  ProgressBar,
  Stat,
  StatRow,
  StatusChip,
} from '../../components';
import * as outboxQ from '../../db/queries/outbox';
import * as photoQ from '../../db/queries/photo';
import * as readFormatQ from '../../db/queries/readFormat';
import * as walkQ from '../../db/queries/readsWalk';
import { useSideBySide } from '../../tablet/columns';
import { useDefaultSelection, usePick } from '../../tablet/selection';
import { useTabletSelection } from '../../tablet/TabletFrame';
import { useTheme } from '../../theme';
import { distanceText, metresBetween } from './figures';
import { PressCard, Spread, Toolbar } from './parts';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { resolveRoute, routeName, streetOf } from './records';
import { useReads } from './services';
import { LocationAsk } from './LocationAsk';

function shortDate(iso: string | null, locale?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' });
}

function time(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

/** A route is on the phone once its stops are (RW-01's two chips). */
function onPhone(r: walkQ.RouteCard): boolean {
  return r.stops > 0;
}

// ── RW-01 My routes ─────────────────────────────────────────────────────────

export function MyRoutes() {
  // RW-01 T: beside the route's summary, the one on show is ruled heavy.
  const picked = useTabletSelection();
  const { t } = useTranslation();
  const go = useGo();
  const { s } = useReads();
  const cards = useLive(() => walkQ.routeCards(s, 50), []);
  const sync = useLive(
    () => ({ items: outboxQ.countUnsentMine(s), photos: photoQ.countWaitingMine(s), last: walkQ.lastSentAt(s) }),
    [],
  );
  const today = cards.filter((c) => c.status !== 'turned_in');
  const turnedIn = cards.filter((c) => c.status === 'turned_in');
  const meters = today.reduce((n, c) => n + c.meters, 0);
  return (
    <ScreenBody
      bar={
        <ActionBar note={t('field.reads.rw01.downloadNote', { meters })}>
          <Button
            variant="primary"
            grow
            testID="door-RW-03"
            onPress={() => go('RW-03', today[0] ? { routeId: today[0].id } : undefined)}
          >
            {t('field.reads.rw01.downloadAll')}
          </Button>
        </ActionBar>
      }
    >
      <Toolbar>
        <IconButton label={t('field.reads.rw01.find')} onPress={() => go('RW-08')} testID="door-RW-08">
          <AppText variant="section">⌕</AppText>
        </IconButton>
      </Toolbar>
      <Card testID="sync-line">
        <Spread>
          <View style={{ flexShrink: 1 }}>
            <AppText variant="body" weight="heavy">
              {t('field.reads.rw01.waiting', { n: sync.items })}
            </AppText>
            <AppText variant="label" tone="muted">
              {sync.last
                ? t('field.reads.rw01.photosLast', { photos: sync.photos, time: time(sync.last) })
                : t('field.reads.rw01.photos', { photos: sync.photos })}
            </AppText>
          </View>
          <Button
            variant="primary"
            size="sm"
            testID="door-RW-26"
            // RW-26 sends as it opens; pressing here only takes the reader there.
            onPress={() => go('RW-26', today[0] ? { routeId: today[0].id } : undefined)}
          >
            {t('field.reads.rw01.sendNow')}
          </Button>
        </Spread>
      </Card>
      <Kicker>{t('field.reads.rw01.today')}</Kicker>
      {today.length === 0 ? (
        <Notice tone="info">{t('field.reads.rw01.none')}</Notice>
      ) : (
        today.map((r, i) => (
          <PressCard
            key={r.id}
            label={routeName(r)}
            emphasis={(picked.split ? (picked.selected ?? today[0]?.id) === r.id : i === 0) ? 'strong' : 'none'}
            onPress={() => go('RW-02', { routeId: r.id })}
            testID={i === 0 ? 'door-RW-02' : `route-${r.id}`}
          >
            <Spread>
              <AppText variant="section">{routeName(r)}</AppText>
              <StatusChip tone={onPhone(r) ? 'success' : 'neutral'}>
                {onPhone(r) ? t('field.reads.rw01.onPhone') : t('field.reads.rw01.notDownloaded')}
              </StatusChip>
            </Spread>
            <AppText variant="label" tone="muted">
              {[r.code, r.service, r.read_type].filter(Boolean).join(' · ')}
            </AppText>
            <StatRow>
              <Stat value={String(r.stops)} caption={t('field.reads.common.stops')} />
              <Stat value={String(r.meters)} caption={t('field.reads.common.meters')} />
              {onPhone(r) ? <Stat value={String(r.read)} caption={t('field.reads.common.read')} /> : null}
            </StatRow>
            <Spread>
              <AppText variant="label" tone="muted">
                {r.window_end ? t('field.reads.rw01.windowCloses', { date: shortDate(r.window_end) }) : ''}
              </AppText>
              <AppText variant="body" weight="heavy">
                {t('field.reads.common.open')}
              </AppText>
            </Spread>
          </PressCard>
        ))
      )}
      {turnedIn.length > 0 ? <Kicker>{t('field.reads.rw01.turnedIn')}</Kicker> : null}
      {turnedIn.length > 0 ? (
        <Card>
          {turnedIn.map((r, i) => (
            <ListRow
              key={r.id}
              divider={i > 0}
              label={routeName(r)}
              detail={t('field.reads.rw01.turnedInLine', { code: r.code ?? '', read: r.read, couldNot: r.could_not })}
              value={shortDate(r.turned_in_at)}
              onPress={() => go('RW-27', { routeId: r.id })}
              testID={i === 0 ? 'door-RW-27' : `turned-${r.id}`}
            />
          ))}
        </Card>
      ) : null}
    </ScreenBody>
  );
}

// ── RW-02 Route summary ─────────────────────────────────────────────────────

export function RouteSummary() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  if (!r) return <NoRoute />;
  const facts: Array<[string, string | null]> = [
    [t('field.reads.rw02.code'), r.code],
    [t('field.reads.rw02.service'), r.service],
    [t('field.reads.rw02.readType'), r.read_type],
    [t('field.reads.rw02.area'), r.area],
    [t('field.reads.rw02.cycle'), r.cycle],
    [t('field.reads.rw02.window'), [shortDate(r.window_start), shortDate(r.window_end)].filter(Boolean).join(' – ') || null],
  ];
  return (
    <ScreenBody
      bar={
        <ActionBar>
          {onPhone(r) ? (
            <Button variant="primary" grow testID="door-RW-05" onPress={() => go('RW-05', { routeId: r.id })}>
              {t('field.reads.rw02.startWalk')}
            </Button>
          ) : null}
          <Button variant={onPhone(r) ? 'secondary' : 'primary'} grow testID="door-RW-03" onPress={() => go('RW-03', { routeId: r.id })}>
            {t('field.reads.rw02.download')}
          </Button>
        </ActionBar>
      }
    >
      <AppText variant="title" testID="route-name">
        {routeName(r)}
      </AppText>
      {/* FB-003: opening the route asks for location where it is not on yet. */}
      <LocationAsk />
      <Card>
        <StatRow>
          <Stat size="title" value={String(r.stops)} caption={t('field.reads.common.stops')} />
          <Stat size="title" value={String(r.meters)} caption={t('field.reads.common.meters')} />
          <Stat size="title" value={String(r.subs)} caption={t('field.reads.common.subMeters')} />
        </StatRow>
      </Card>
      <Card>
        {facts
          .filter(([, v]) => v)
          .map(([label, value], i) => (
            <ListRow key={label} divider={i > 0} label={label} value={value ?? ''} />
          ))}
      </Card>
      {r.notes ? (
        <Card title={t('field.reads.rw02.notes')}>
          <AppText variant="body">{r.notes}</AppText>
        </Card>
      ) : null}
      <Card>
        <ListRow
          label={t('field.reads.rw02.seeMap')}
          onPress={() => go('RW-04', { routeId: r.id })}
          testID="door-RW-04"
        />
      </Card>
    </ScreenBody>
  );
}

function NoRoute() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <Notice tone="info">{t('field.reads.common.noRoute')}</Notice>
      <Button testID="door-RW-01" onPress={() => go('RW-01')}>
        {t('field.reads.common.myRoutes')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-03 Download ──────────────────────────────────────────────────────────

/**
 * The parts of a route the walk needs, each checked against what is ON the
 * phone rather than trusted from a progress callback. *Map tiles* are not a
 * part: offline maps are out of scope (`01-overview.md` §5).
 */
export function routeParts(s: ReturnType<typeof useReads>['s'], routeId: string) {
  const r = walkQ.routeCard(s, routeId);
  const meters = walkQ.stops(s, routeId, { order: 'walk' });
  const reads = meters.flatMap((st) => walkQ.metersAtStop(s, st.id));
  const withCustomer = reads.filter((m) => m.account_id === null || m.customer_name !== null).length;
  return [
    { id: 'stops', done: (r?.stops ?? 0) > 0, count: r?.stops ?? 0 },
    { id: 'meters', done: reads.length > 0, count: reads.length },
    { id: 'access', done: meters.length > 0, count: meters.filter((m) => m.access_notes || m.hazard).length },
    { id: 'customers', done: reads.length > 0 && withCustomer === reads.length, count: withCustomer },
  ];
}

export function Download() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const parts = useLive(() => (r ? routeParts(s, r.id) : []), [r?.id]);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!services.downloadRoutes) return;
    services
      .downloadRoutes()
      .then(bump)
      .catch(() => setFailed(true));
  }, [services, bump]);
  const done = parts.filter((p) => p.done).length;
  const pct = parts.length ? Math.round((done / parts.length) * 100) : 0;
  const ready = parts.length > 0 && done === parts.length;
  const words: Record<string, string> = {
    stops: t('field.reads.rw03.stops', { n: parts[0]?.count ?? 0 }),
    meters: t('field.reads.rw03.meters', { n: parts[1]?.count ?? 0 }),
    access: t('field.reads.rw03.access'),
    customers: t('field.reads.rw03.customers'),
  };
  return (
    <ScreenBody
      bar={
        <ActionBar note={ready ? undefined : t('field.reads.rw03.opensAt')}>
          <Button
            variant="primary"
            grow
            disabled={!ready}
            testID="door-RW-05"
            onPress={() => go('RW-05', r ? { routeId: r.id } : undefined)}
          >
            {t('field.reads.rw03.start')}
          </Button>
        </ActionBar>
      }
    >
      <AppText variant="title" style={{ textAlign: 'center' }} testID="download-percent">
        {`${pct}%`}
      </AppText>
      <AppText variant="body" tone="muted" style={{ textAlign: 'center' }}>
        {t('field.reads.rw03.finish')}
      </AppText>
      <ProgressBar tone="strong" done={done} total={parts.length} label={`${pct}%`} />
      <Card>
        {parts.map((p, i) => (
          <ListRow
            key={p.id}
            divider={i > 0}
            label={words[p.id] ?? p.id}
            leading={<AppText variant="section">{p.done ? '✓' : '○'}</AppText>}
            testID={`part-${p.id}-${p.done ? 'done' : 'todo'}`}
          />
        ))}
      </Card>
      {!services.downloadRoutes ? <Notice tone="info">{t('field.reads.rw03.noDownload')}</Notice> : null}
      {failed ? <Notice tone="danger">{t('field.reads.rw03.failed')}</Notice> : null}
    </ScreenBody>
  );
}

// ── RW-04 Route map ─────────────────────────────────────────────────────────

type Pin = 'next' | 'read' | 'couldNot' | 'toDo';

function pinOf(st: walkQ.StopCard, nextId: string | null): Pin {
  if (st.id === nextId) return 'next';
  if (st.could_not > 0) return 'couldNot';
  if (st.unread === 0) return 'read';
  return 'toDo';
}

/**
 * The stops on a plain plot, by the points that came with the route — no
 * tiles (offline maps are out of scope), so it works with no signal.
 */
export function RouteMap() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, here } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const all = useLive(() => (r ? walkQ.stops(s, r.id, { order: 'walk' }) : []), [r?.id]);
  const nearest = useLive(
    () => (r ? walkQ.stops(s, r.id, { order: 'nearest', from: here, filter: 'left', limit: 1 })[0] ?? null : null),
    [r?.id, here?.lat, here?.lng],
  );
  const placed = all.filter((x) => x.lat !== null && x.lng !== null);
  const pts = [...placed.map((x) => ({ lat: x.lat as number, lng: x.lng as number })), ...(here ? [here] : [])];
  const box = useMemo(() => {
    const lats = pts.map((p) => p.lat);
    const lngs = pts.map((p) => p.lng);
    return { minLat: Math.min(...lats), maxLat: Math.max(...lats), minLng: Math.min(...lngs), maxLng: Math.max(...lngs) };
  }, [pts]);
  const at = (p: { lat: number; lng: number }) => {
    const x = box.maxLng === box.minLng ? 0.5 : (p.lng - box.minLng) / (box.maxLng - box.minLng);
    const y = box.maxLat === box.minLat ? 0.5 : (box.maxLat - p.lat) / (box.maxLat - box.minLat);
    return { left: `${5 + x * 85}%` as const, top: `${5 + y * 85}%` as const };
  };
  const colour: Record<Pin, string> = {
    next: theme.colors.text,
    read: theme.colors.status.success.rule,
    couldNot: theme.colors.status.warning.rule,
    toDo: theme.colors.textMuted,
  };
  const left = all.filter((x) => x.unread > 0).length;
  return (
    <ScreenBody
      scroll={false}
      bar={
        <ActionBar>
          <Button grow testID="door-RW-05" onPress={() => go('RW-05', r ? { routeId: r.id } : undefined)}>
            {t('field.reads.rw04.list')}
          </Button>
          <Button
            variant="primary"
            grow
            disabled={!nearest}
            testID="door-RW-06"
            onPress={() => nearest && go('RW-06', { stopId: nearest.id })}
          >
            {t('field.reads.rw04.nearest')}
          </Button>
        </ActionBar>
      }
    >
      <AppText variant="body" weight="heavy" style={{ textAlign: 'right' }}>
        {t('field.reads.rw04.left', { n: left })}
      </AppText>
      <View
        testID="route-plot"
        style={{ flex: 1, backgroundColor: theme.colors.surface, borderColor: theme.colors.border, borderWidth: theme.borderWidth.card }}
      >
        {placed.map((x) => {
          const pin = pinOf(x, nearest?.id ?? null);
          return (
            <View
              key={x.id}
              accessible
              accessibilityLabel={`${streetOf(x)} · ${t(`field.reads.rw04.pin.${pin}`)}`}
              testID={`pin-${x.id}-${pin}`}
              style={{
                position: 'absolute',
                ...at({ lat: x.lat as number, lng: x.lng as number }),
                width: theme.space[6],
                height: theme.space[6],
                backgroundColor: colour[pin],
                borderColor: theme.colors.card,
                borderWidth: theme.borderWidth.emphasis,
              }}
            />
          );
        })}
        {here ? (
          <View
            accessible
            accessibilityLabel={t('field.reads.rw04.you')}
            testID="pin-you"
            style={{
              position: 'absolute',
              ...at(here),
              width: theme.space[6],
              height: theme.space[6],
              borderRadius: theme.space[3],
              backgroundColor: theme.colors.status.info.rule,
            }}
          />
        ) : null}
      </View>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[4] }}>
        {(['next', 'read', 'couldNot', 'toDo'] as const).map((p) => (
          <View key={p} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[1] }}>
            <View style={{ width: theme.space[3], height: theme.space[3], borderRadius: theme.space[2], backgroundColor: colour[p] }} />
            <AppText variant="label">{t(`field.reads.rw04.pin.${p}`)}</AppText>
          </View>
        ))}
      </View>
    </ScreenBody>
  );
}

// ── RW-05 The walk ──────────────────────────────────────────────────────────

function stopLine(t: TFunction, st: walkQ.StopCard): { text: string; warn: boolean } {
  if (st.could_not > 0 && st.last_reason) return { text: t('field.reads.rw05.cameBack', { reason: st.last_reason }), warn: true };
  return { text: t('field.reads.rw05.metersAtStop', { n: st.meters, position: st.walk_position }), warn: false };
}

export function TheWalk() {
  const { t } = useTranslation();
  const theme = useTheme();
  // The stop beside the list only where the PANE holds two columns of 260
  // (R122), never because the window is a tablet.
  const tablet = useSideBySide();
  const go = useGo();
  const params = useParams();
  const { s, here, settings, services } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  // DEF-FLD-10598: the route names a form version this phone does not hold.
  const noForm = useLive(() => (r ? readFormatQ.missingVersion(s, services.db, r.id) : false), [r?.id]);
  const [order, setOrder] = useState<'nearest' | 'walk'>(settings.order);
  const nearestUsable = order === 'nearest' && here !== null;
  const list = useLive(
    () => (r ? walkQ.stops(s, r.id, { order: nearestUsable ? 'nearest' : 'walk', from: here, filter: 'left' }) : []),
    [r?.id, nearestUsable, here?.lat, here?.lng],
  );
  const tally = useLive(() => (r ? walkQ.tally(s, r.id) : null), [r?.id]);
  const [picked, setPicked] = useState<string | null>(null);
  // RW-05 T: beside the stop, the frame's pick is the chosen stop (the
  // nearest until one is picked) and a card's door to RW-06 picks it.
  const framePick = usePick();
  const firstId = list[0]?.id ?? null;
  useDefaultSelection(firstId);
  if (!r || !tally) return <NoRoute />;
  const first = list[0] ?? null;
  const chosen = list.find((x) => x.id === (framePick.active ? framePick.selected : picked)) ?? first;
  const away = (st: walkQ.StopCard) =>
    here && st.lat !== null && st.lng !== null ? distanceText(metresBetween(here, { lat: st.lat, lng: st.lng })) : '';
  const rows = (
    <View style={{ gap: theme.space[2] }}>
      {/* FB-003: walking the route asks for location where it is not on yet. */}
      <LocationAsk />
      {noForm ? (
        <Notice tone="warning" testID="walk-no-form">
          {t('field.reads.rw05.noForm')}
        </Notice>
      ) : null}
      <ChoiceChips
        label={t('field.reads.rw05.order')}
        fill
        active={order}
        onSelect={(id) => setOrder(id as 'nearest' | 'walk')}
        segments={[
          { id: 'nearest', label: t('field.reads.rw05.nearest') },
          { id: 'walk', label: t('field.reads.rw05.walkOrder') },
        ]}
        testID="walk-order"
      />
      <AppText variant="label" tone="muted">
        {order === 'nearest' && !here ? t('field.reads.rw05.noFix') : order === 'nearest' ? t('field.reads.rw05.anyOrder') : t('field.reads.rw05.officeOrder')}
      </AppText>
      {list.length === 0 ? <Notice tone="success">{t('field.reads.rw05.allDone')}</Notice> : null}
      {list.map((st, i) => {
        const line = stopLine(t, st);
        return (
          <PressCard
            key={st.id}
            label={streetOf(st)}
            emphasis={st.id === chosen?.id ? 'strong' : line.warn ? 'warning' : 'none'}
            onPress={() => (tablet ? setPicked(st.id) : go('RW-06', { stopId: st.id }))}
            testID={`stop-${i}`}
          >
            <Spread>
              <View style={{ flexShrink: 1 }}>
                <AppText variant="body" weight="heavy">
                  {streetOf(st)}
                </AppText>
                <AppText variant="label" style={line.warn ? { color: theme.colors.statusInk.warning } : undefined} tone={line.warn ? undefined : 'muted'}>
                  {line.text}
                </AppText>
              </View>
              <AppText variant="body" weight="heavy">
                {away(st)}
              </AppText>
            </Spread>
          </PressCard>
        );
      })}
    </View>
  );
  const head = (
    <View style={{ gap: theme.space[1] }}>
      <Spread>
        <AppText variant="title">{routeName(r)}</AppText>
        <IconButton label={t('field.reads.rw05.map')} onPress={() => go('RW-04', { routeId: r.id })} testID="door-RW-04">
          <AppText variant="section">⌖</AppText>
        </IconButton>
      </Spread>
      <ProgressBar done={tally.done} problem={tally.could_not} total={tally.total} label={t('field.reads.rw05.progress', { read: tally.done, total: tally.total })} />
      <Spread>
        <AppText variant="label" tone="muted" testID="walk-progress">
          {t('field.reads.rw05.progressLine', { read: tally.done, total: tally.total, couldNot: tally.could_not })}
        </AppText>
        <Button size="sm" onPress={() => go('RW-22', { routeId: r.id })} testID="door-RW-22">
          {t('field.reads.rw05.progressLink')}
        </Button>
      </Spread>
    </View>
  );
  const bar = (
    <ActionBar>
      <IconButton outlined label={t('field.reads.rw05.scanUnlisted')} onPress={() => go('RW-19', chosen ? { stopId: chosen.id } : { routeId: r.id })} testID="door-RW-19">
        <AppText variant="section">⌗</AppText>
      </IconButton>
      <Button variant="primary" grow disabled={!chosen} testID="door-RW-06" onPress={() => chosen && go('RW-06', { stopId: chosen.id })}>
        {chosen ? t('field.reads.rw05.openStop', { address: streetOf(chosen) }) : t('field.reads.rw05.openNone')}
      </Button>
    </ActionBar>
  );
  if (tablet && chosen) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: theme.colors.page }}>
        <View style={{ flex: 1 }}>
          <ScreenBody>
            {head}
            {rows}
          </ScreenBody>
        </View>
        <View style={{ flex: 1 }} testID="walk-detail">
          <ScreenBody bar={bar}>
            <Card>
              <AppText variant="section">{streetOf(chosen)}</AppText>
              <AppText variant="label" tone="muted">
                {[t('field.reads.rw05.metersAtStop', { n: chosen.meters, position: chosen.walk_position }), away(chosen)].filter(Boolean).join(' · ')}
              </AppText>
              {chosen.hazard ? <Notice tone="danger">{chosen.hazard}</Notice> : null}
              {chosen.access_notes ? <AppText variant="body">{chosen.access_notes}</AppText> : null}
            </Card>
          </ScreenBody>
        </View>
      </View>
    );
  }
  return (
    <ScreenBody bar={bar}>
      {head}
      {rows}
    </ScreenBody>
  );
}
