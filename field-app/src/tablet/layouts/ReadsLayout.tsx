/**
 * The reading route on a tablet (T-29). Each keeps the phone screen as its
 * list and draws the board's detail beside it from the same handset store
 * (`db/queries/readsWalk`), through the same reads services:
 *
 * RW-05 T *The walk* and RW-23 T *Still to do* — the walk (or what is left)
 *   with a stop's door to RW-06 picking it (`SelectOnOpen`); beside it the
 *   stop (`StopSummary`): its address, how many meters and its place in the
 *   walk, how far, the hazard in the danger ink, how to get in, and *On the
 *   map* (RW-04) · *Open the stop* (RW-06).
 * RW-06 T *The stop* — the meters at the address, a card picking its meter;
 *   beside it the meter (`MeterSummary`): who and which unit, the meter and
 *   badge, the service, the last reading and what is expected now (R79,
 *   R80), and *Can't read here* (RW-17) · *Read* (RW-09, or RW-11 when *Scan
 *   before reading* is on) · *Access and notes* (RW-07); a master opens its
 *   subs (RW-12).
 * RW-08 T *Find a meter* — the search, a hit's door to RW-09 picking it;
 *   beside it the same `MeterSummary`. ⚠ The board draws no act on this
 *   detail; *Read* is kept (OUR JUDGMENT, reported) because on a phone the
 *   hit itself opens the reading, and a found meter with no way to read it
 *   would be a dead end.
 * RW-12 T *Master and subs* — the master and its subs; beside them *So far*
 *   (`BalanceCard`, the phone's) and *Read Unit 3*, the next unread.
 * RW-28 T *My reads* — the routes read, a route's door to RW-27 picking it;
 *   beside it the totals of the picked route's period — read, could not be,
 *   routes — exactly the figures the phone shows on that tab, and *Open*
 *   (RW-27).
 * RW-29 T *Reading settings* — the settings, listed (`PickList`: the phone
 *   screen is the cards themselves); beside the pick its card — the keypad
 *   with the order under it, as drawn — and *More in Settings* (FF-51).
 *   *Dictation* is not listed: the phone does not build it (no speech
 *   library, `screens/reads/mine.tsx`).
 *
 * The boards' rationale paragraphs are not on screen (B14 rule 33).
 */
import { type ComponentType } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Button, Card, Notice, Stat, StatRow } from '../../components';
import { type Fact } from '../../components/Facts';
import * as walkQ from '../../db/queries/readsWalk';
import { useHandsetPrefs } from '../../screens/me/hooks';
import { PhotosWifiOnlyRow } from '../../screens/me/SettingsScreen';
import { distanceText, group, metresBetween } from '../../screens/reads/figures';
import { KeypadCard, MyReads, OrderCard, periodOf, READING_SWITCHES, type ReadingSwitch, ReadingSwitchRow } from '../../screens/reads/mine';
import { StillToDo } from '../../screens/reads/progress';
import { readsScreen, useGo, useLive } from '../../screens/reads/ReadsScreen';
import { meterName, routeName, streetOf, unitLabel } from '../../screens/reads/records';
import { TheWalk } from '../../screens/reads/route';
import { useOptionalReads, useReads } from '../../screens/reads/services';
import { BalanceCard, FindMeter, MasterAndSubs, TheStop } from '../../screens/reads/stop';
import { DetailCard, DetailNone, DetailPane } from '../DetailPane';
import { PickList } from '../Pickable';
import { SelectOnOpen, useSelectedOr } from '../selection';


/**
 * A detail pane of a reading board renders only where the reads services are
 * mounted — as `readsScreen` does for the phone screen beside it, which shows
 * its placeholder there instead (a store-less mount, the frame sweep).
 */
function readsPane(Body: ComponentType): ComponentType {
  function Pane() {
    return useOptionalReads() ? <Body /> : null;
  }
  Pane.displayName = `ReadsPane(${Body.name})`;
  return Pane;
}

// ── a stop, beside the walk or what is left ───────────────────────────────

function StopSummary(props: { testID: string; mapLabel: string; openLabel: string }) {
  const { t } = useTranslation();
  const go = useGo();
  const { s, here } = useReads();
  const id = useSelectedOr('stopId');
  const stop = useLive(() => (id ? (walkQ.stop(s, id) ?? null) : null), [id]);
  if (!stop) return <DetailNone title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID={props.testID} />;
  const away = here && stop.lat !== null && stop.lng !== null ? distanceText(metresBetween(here, { lat: stop.lat, lng: stop.lng })) : null;
  const facts: Fact[] = [];
  if (stop.access_notes) facts.push({ label: t('field.tablet.rw05.gettingIn'), value: stop.access_notes });
  if (stop.unread > 0) facts.push({ label: t('field.tablet.rw05.toRead'), value: t('field.reads.common.nOfM', { n: stop.unread, m: stop.meters }) });
  if (stop.last_reason) facts.push({ label: t('field.tablet.rw05.lastTime'), value: stop.last_reason });
  return (
    <DetailPane
      testID={props.testID}
      acts={
        <>
          <Button grow onPress={() => go('RW-04', { routeId: stop.route_id })} testID="pane-RW-04">
            {props.mapLabel}
          </Button>
          <Button grow variant="primary" onPress={() => go('RW-06', { stopId: stop.id })} testID="pane-RW-06">
            {props.openLabel}
          </Button>
        </>
      }
    >
      <DetailCard
        title={streetOf(stop)}
        line={[t('field.reads.rw05.metersAtStop', { n: stop.meters, position: stop.walk_position }), away].filter(Boolean).join(' · ')}
        facts={facts}
        testID={`${props.testID}-card`}
      >
        {stop.hazard ? (
          <Notice tone="danger" testID={`${props.testID}-hazard`}>
            {stop.hazard}
          </Notice>
        ) : null}
      </DetailCard>
    </DetailPane>
  );
}

// ── RW-05 The walk ────────────────────────────────────────────────────────

const Walk = readsScreen('RW-05', TheWalk);

export function WalkList() {
  return (
    <SelectOnOpen opens="RW-06" param="stopId">
      <Walk />
    </SelectOnOpen>
  );
}

function WalkStopBody() {
  const { t } = useTranslation();
  return <StopSummary testID="walk-stop" mapLabel={t('field.tablet.onTheMap')} openLabel={t('field.tablet.rw05.openStop')} />;
}

// ── RW-23 Still to do ─────────────────────────────────────────────────────

const ToDo = readsScreen('RW-23', StillToDo);

export function StillList() {
  return (
    <SelectOnOpen opens="RW-06" param="stopId">
      <ToDo />
    </SelectOnOpen>
  );
}

function StillStopBody() {
  const { t } = useTranslation();
  return <StopSummary testID="still-stop" mapLabel={t('field.reads.rw23.onMap')} openLabel={t('field.tablet.openIt')} />;
}

// ── a meter, beside the stop or the search ────────────────────────────────

function MeterSummary(props: { testID: string; access: boolean }) {
  const { t } = useTranslation();
  const go = useGo();
  const { s, settings } = useReads();
  const id = useSelectedOr('readId');
  const m = useLive(() => (id ? (walkQ.meter(s, id) ?? null) : null), [id]);
  const subs = useLive(() => (m ? walkQ.subsOf(s, m.route_id, m.asset_id) : []), [m?.id]);
  if (!m) return <DetailNone title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID={props.testID} />;
  const unit = unitLabel(m);
  const facts: Fact[] = [{ label: t('field.tablet.rw06.meter'), value: meterName(m) }];
  if (m.badge) facts.push({ label: t('field.tablet.rw06.badge'), value: m.badge });
  if (m.asset_service) facts.push({ label: t('field.tablet.rw06.service'), value: m.asset_service });
  if (m.address_line) facts.push({ label: t('field.tablet.rw06.where'), value: [m.address_line, unit].filter(Boolean).join(', ') });
  if (m.value !== null) facts.push({ label: t('field.tablet.rw06.readNow'), value: `${group(m.value)} ${m.unit}` });
  else if (m.previous_value) facts.push({ label: t('field.tablet.rw06.lastRead'), value: `${group(m.previous_value)} ${m.unit}` });
  if (m.value === null && m.expected_min && m.expected_max) {
    facts.push({ label: t('field.reads.common.expected'), value: `${group(m.expected_min)}–${group(m.expected_max)} ${m.unit}` });
  }
  const unread = m.state === 'unread';
  const isMaster = subs.length > 0;
  return (
    <DetailPane
      testID={props.testID}
      acts={
        <>
          {unread && !isMaster ? (
            <Button grow onPress={() => go('RW-17', { readId: m.id })} testID="pane-RW-17">
              {t('field.reads.rw06.cantRead')}
            </Button>
          ) : null}
          {unread && !isMaster ? (
            <Button
              grow
              variant="primary"
              onPress={() => go(settings.scanFirst ? 'RW-11' : 'RW-09', { readId: m.id })}
              testID={settings.scanFirst ? 'pane-RW-11' : 'pane-RW-09'}
            >
              {t('field.reads.rw12.readNext', { name: unit ?? meterName(m) })}
            </Button>
          ) : null}
          {isMaster ? (
            <Button grow variant="primary" onPress={() => go('RW-12', { readId: m.id })} testID="pane-RW-12">
              {t('field.reads.rw06.readAll')}
            </Button>
          ) : null}
          {props.access ? (
            <Button grow onPress={() => go('RW-07', { stopId: m.stop_id })} testID="pane-RW-07">
              {t('field.reads.rw06.access')}
            </Button>
          ) : null}
        </>
      }
    >
      <DetailCard
        title={m.customer_name ?? t('field.reads.common.noCustomer')}
        line={[unit, m.account_number].filter(Boolean).join(' · ')}
        facts={facts}
        testID={`${props.testID}-card`}
      />
    </DetailPane>
  );
}

// ── RW-06 The stop ────────────────────────────────────────────────────────

const Stop = readsScreen('RW-06', TheStop);

export function StopList() {
  return <Stop />;
}

function StopMeterBody() {
  return <MeterSummary testID="stop-meter" access />;
}

// ── RW-08 Find a meter ────────────────────────────────────────────────────

const Find = readsScreen('RW-08', FindMeter);

export function FindList() {
  return (
    <SelectOnOpen opens="RW-09" param="readId">
      <Find />
    </SelectOnOpen>
  );
}

function FoundMeterBody() {
  return <MeterSummary testID="found-meter" access={false} />;
}

// ── RW-12 Master and subs ─────────────────────────────────────────────────

const Master = readsScreen('RW-12', MasterAndSubs);

export function MasterList() {
  return <Master />;
}

function MasterBalanceBody() {
  const { t } = useTranslation();
  const go = useGo();
  const { s } = useReads();
  const readId = useSelectedOr('readId');
  const master = useLive(() => (readId ? (walkQ.meter(s, readId) ?? null) : null), [readId]);
  const subs = useLive(() => (master ? walkQ.subsOf(s, master.route_id, master.asset_id) : []), [master?.id]);
  if (!master) return <DetailNone title={t('field.reads.common.noMeter')} helper={t('field.tablet.pickHelp')} testID="master-balance" />;
  const next = [master, ...subs].find((m) => m.state === 'unread') ?? null;
  return (
    <DetailPane
      testID="master-balance"
      acts={
        next ? (
          <Button grow variant="primary" onPress={() => go('RW-09', { readId: next.id })} testID="pane-RW-09">
            {t('field.reads.rw12.readNext', { name: unitLabel(next) ?? meterName(next) })}
          </Button>
        ) : undefined
      }
    >
      <BalanceCard master={master} subs={subs} />
    </DetailPane>
  );
}

// ── RW-28 My reads ────────────────────────────────────────────────────────

const Mine = readsScreen('RW-28', MyReads);

export function MineList() {
  return (
    <SelectOnOpen opens="RW-27" param="routeId">
      <Mine />
    </SelectOnOpen>
  );
}

function MineTotalsBody() {
  const { t } = useTranslation();
  const go = useGo();
  const { s, services } = useReads();
  const cards = useLive(() => walkQ.routeCards(s, 200), []);
  const id = useSelectedOr('routeId');
  const now = services.clock.now();
  const latest = [...cards].sort((a, b) => (b.window_start ?? '').localeCompare(a.window_start ?? ''))[0]?.cycle ?? null;
  const picked = cards.find((c) => c.id === id) ?? null;
  const period = picked ? periodOf(picked, now, latest) : 'week';
  const shown = cards.filter((c) => c.done > 0 && periodOf(c, now, latest) === period);
  const read = shown.reduce((n, c) => n + c.read, 0);
  const could = shown.reduce((n, c) => n + c.could_not, 0);
  return (
    <DetailPane
      testID="mine-totals"
      acts={
        picked ? (
          <Button grow onPress={() => go('RW-27', { routeId: picked.id })} testID="pane-RW-27">
            {t('field.tablet.rw28.open', { route: routeName(picked) })}
          </Button>
        ) : undefined
      }
    >
      <Card testID="mine-totals-card">
        <StatRow>
          <Stat size="title" value={String(read)} caption={t('field.reads.common.read')} testID="mine-totals-read" />
          <Stat size="title" value={String(could)} caption={t('field.reads.common.couldNot')} testID="mine-totals-could-not" />
          <Stat size="title" value={String(shown.length)} caption={t('field.reads.rw28.routes')} testID="mine-totals-routes" />
        </StatRow>
      </Card>
    </DetailPane>
  );
}

// ── RW-29 Reading settings ────────────────────────────────────────────────

const SWITCH_TITLE: Record<ReadingSwitch, string> = {
  confirmEach: 'field.reads.rw29.confirm',
  scanFirst: 'field.reads.rw29.scanFirst',
};

function ReadingListBody() {
  const { t } = useTranslation();
  const { settings } = useReads();
  const [prefs] = useHandsetPrefs();
  const on = (v: boolean) => (v ? t('field.tablet.on') : t('field.tablet.off'));
  const items = [
    { id: 'keypad', title: t('field.reads.rw29.keypad'), value: t(`field.reads.rw29.${settings.keypad}`) },
    {
      id: 'order',
      title: t('field.reads.rw29.order'),
      value: settings.order === 'nearest' ? t('field.reads.rw05.nearest') : t('field.reads.rw05.walkOrder'),
    },
    ...READING_SWITCHES.map((w) => ({ id: w, title: t(SWITCH_TITLE[w]), value: on(settings[w]) })),
    // DEF-FLD-10640 — the one photo switch, FF-51's.
    { id: 'photosWifiOnly', title: t('field.ff51.photosWifiOnly'), value: on(prefs.photosWifiOnly) },
  ];
  return (
    <View style={{ flex: 1 }} testID="screen-RW-29">
      <PickList kicker={t('field.tablet.rw29.reading')} items={items} testID="reading-list" />
    </View>
  );
}

function ReadingDetailBody() {
  const { t } = useTranslation();
  const go = useGo();
  const which = useSelectedOr('setting') ?? 'keypad';
  return (
    <DetailPane
      testID="reading-detail"
      acts={
        <Button grow onPress={() => go('FF-51')} testID="pane-FF-51">
          {t('field.reads.rw29.more')}
        </Button>
      }
    >
      {which === 'keypad' ? (
        <>
          <KeypadCard />
          <OrderCard />
        </>
      ) : which === 'order' ? (
        <OrderCard />
      ) : which === 'photosWifiOnly' ? (
        <Card>
          <PhotosWifiOnlyRow />
        </Card>
      ) : (
        <Card>
          <ReadingSwitchRow which={which as ReadingSwitch} />
        </Card>
      )}
    </DetailPane>
  );
}

export const WalkStop = readsPane(WalkStopBody);
export const StillStop = readsPane(StillStopBody);
export const StopMeter = readsPane(StopMeterBody);
export const FoundMeter = readsPane(FoundMeterBody);
export const MasterBalance = readsPane(MasterBalanceBody);
export const MineTotals = readsPane(MineTotalsBody);
export const ReadingList = readsPane(ReadingListBody);
export const ReadingDetail = readsPane(ReadingDetailBody);
