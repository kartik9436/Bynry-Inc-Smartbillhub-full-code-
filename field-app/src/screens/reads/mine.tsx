/**
 * The reader's own — RW-28 My reads and RW-29 Reading settings (EP-FLD-14,
 * EP-FLD-09). Built from `wireframes/reads/RW-28, 29*.png`.
 *
 * RW-28 (R120): what was read, never how fast — no rate, no ranking.
 * *This week* is the last seven days of readings; *This cycle* is the routes
 * of the reader's latest cycle code; *Earlier* is everything else on the
 * phone (turned-in routes clear themselves after the retention period).
 *
 * FB-030 (PO 2026-10-31): the list is PAGED in SQL (`readsWalk.mineCards`,
 * 50 a page, *Show more*, no cap) — it read the first 200 routes and filtered
 * them here until then — and the totals count every route of the tab
 * (`mineTotals`). A route opens RW-27, which now lists every reading taken on
 * it; a reading opens its record HERE, RW-28 pushed with a `readId`
 * (`readingRecord.tsx`). History is 14 days on the phone, refilled from the
 * server on a new phone (`sync/routeHistory.ts`).
 *
 * RW-29 draws two rows not built here, each for want of something the app
 * does not have rather than by choice: *Sound on each save* (no audio library
 * is installed) and *Dictation · English* (no speech library — see
 * `ports.ts`). A switch that does nothing is a dead control (hard-won law 2's
 * mirror), so they wait for the library rather than ship as decoration.
 * *Photos on mobile data* is stored here; the photo uploader must read it
 * (`reads.settings`), reported to the coordinator.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, ChoiceChips, Notice, Stat, StatRow, ToggleRow } from '../../components';
import * as walkQ from '../../db/queries/readsWalk';
import { useDefaultSelection } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { PhotosWifiOnlyRow } from '../me/SettingsScreen';
import { PressCard, Spread } from './parts';
import { ReadingRecord } from './readingRecord';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { routeName } from './records';
import { useReads } from './services';

type Period = 'week' | 'cycle' | 'earlier';

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;
/** FB-030 — RW-28 pages its routes (NFR-3); *Show more* adds a page. */
export const MINE_PAGE = 50;

/** Which tab a route belongs on — exported for the test that pins the split. */
export function periodOf(r: walkQ.RouteCard, now: Date, latestCycle: string | null): Period {
  const at = r.last_captured_at ?? r.turned_in_at;
  if (at && now.getTime() - Date.parse(at) <= WEEK_MS) return 'week';
  if (latestCycle && r.cycle === latestCycle) return 'cycle';
  return 'earlier';
}

// ── RW-28 My reads ──────────────────────────────────────────────────────────

export function MyReads() {
  const { readId } = useParams();
  if (readId) {
    return (
      <ScreenBody>
        <ReadingRecord readId={readId} />
      </ScreenBody>
    );
  }
  return <MyReadsList />;
}

function MyReadsList() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const { s, services } = useReads();
  const [period, setPeriod] = useState<Period>('week');
  const [pages, setPages] = useState(1);
  const now = services.clock.now();
  const weekFrom = new Date(now.getTime() - WEEK_MS).toISOString();
  const latest = useLive(() => walkQ.latestCycle(s), []);
  const page = useLive(
    () => walkQ.mineCards(s, { period, weekFrom, latest, limit: MINE_PAGE * pages + 1 }),
    [period, pages, latest, weekFrom.slice(0, 16)],
  );
  const totals = useLive(() => walkQ.mineTotals(s, { period, weekFrom, latest }), [period, latest, weekFrom.slice(0, 16)]);
  const shown = page.slice(0, MINE_PAGE * pages);
  // RW-28 T: beside the totals, the first route of the period is picked.
  useDefaultSelection(shown[0]?.id ?? null);
  const read = totals.read;
  const could = totals.could_not;
  return (
    <ScreenBody>
      <ChoiceChips
        label={t('field.screen.rw28')}
        active={period}
        onSelect={(id) => {
          setPeriod(id as Period);
          setPages(1);
        }}
        segments={[
          { id: 'week', label: t('field.reads.rw28.week') },
          { id: 'cycle', label: t('field.reads.rw28.cycle') },
          { id: 'earlier', label: t('field.reads.rw28.earlier') },
        ]}
        testID="period"
      />
      <Card>
        <StatRow>
          <Stat size="title" value={String(read)} caption={t('field.reads.common.read')} testID="mine-read" />
          <Stat size="title" value={String(could)} caption={t('field.reads.common.couldNot')} testID="mine-could-not" />
          <Stat size="title" value={String(totals.routes)} caption={t('field.reads.rw28.routes')} testID="mine-routes" />
        </StatRow>
      </Card>
      {shown.length === 0 ? <Notice tone="info">{t('field.reads.rw28.none')}</Notice> : null}
      {shown.map((c, i) => {
        const trouble = c.refused > 0;
        const detail = [
          c.code,
          t('field.reads.common.nOfM', { n: c.done, m: c.meters }),
          trouble ? t('field.reads.rw28.refused', { n: c.refused }) : c.could_not ? t('field.reads.rw28.withReason', { n: c.could_not }) : null,
        ]
          .filter(Boolean)
          .join(' · ');
        return (
          <PressCard key={c.id} label={routeName(c)} onPress={() => go('RW-27', { routeId: c.id })} testID={i === 0 ? 'door-RW-27' : `mine-${c.id}`}>
            <Spread>
              <View style={{ flexDirection: 'row', gap: theme.space[3], flexShrink: 1 }}>
                <AppText variant="section" style={{ color: trouble ? theme.colors.statusInk.warning : theme.colors.statusInk.success }}>
                  {trouble ? '!' : '✓'}
                </AppText>
                <View style={{ flexShrink: 1 }}>
                  <AppText variant="body" weight="heavy">
                    {routeName(c)}
                  </AppText>
                  <AppText variant="label" tone="muted">
                    {detail}
                  </AppText>
                </View>
              </View>
            </Spread>
          </PressCard>
        );
      })}
      {page.length > shown.length ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="mine-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
      <Notice tone="info">{t('field.reads.rw28.notHowFast')}</Notice>
    </ScreenBody>
  );
}

// ── RW-29 Reading settings ──────────────────────────────────────────────────
//
// Each card is its own component (B14 rule 43): the tablet board (RW-29 T)
// lists the settings and shows one beside the list.

export function KeypadCard() {
  const { t } = useTranslation();
  const { settings, setSettings } = useReads();
  return (
    <Card title={t('field.reads.rw29.keypad')}>
      <ChoiceChips
        label={t('field.reads.rw29.keypad')}
        fill
        active={settings.keypad}
        onSelect={(id) => setSettings({ ...settings, keypad: id as typeof settings.keypad })}
        segments={[
          { id: 'normal', label: t('field.reads.rw29.normal') },
          { id: 'large', label: t('field.reads.rw29.large') },
          { id: 'largest', label: t('field.reads.rw29.largest') },
        ]}
        testID="set-keypad"
      />
      <AppText variant="label" tone="muted">
        {t('field.reads.rw29.forGloves')}
      </AppText>
    </Card>
  );
}

export function OrderCard() {
  const { t } = useTranslation();
  const { settings, setSettings } = useReads();
  return (
    <Card title={t('field.reads.rw29.order')}>
      <ChoiceChips
        label={t('field.reads.rw29.order')}
        fill
        active={settings.order}
        onSelect={(id) => setSettings({ ...settings, order: id as typeof settings.order })}
        segments={[
          { id: 'nearest', label: t('field.reads.rw05.nearest') },
          { id: 'walk', label: t('field.reads.rw05.walkOrder') },
        ]}
        testID="set-order"
      />
      <AppText variant="label" tone="muted">
        {t('field.reads.rw29.opensOn')}
      </AppText>
    </Card>
  );
}

export const READING_SWITCHES = ['confirmEach', 'scanFirst'] as const;
export type ReadingSwitch = (typeof READING_SWITCHES)[number];

const SWITCH: Record<ReadingSwitch, { label: string; detail: string; testID: string }> = {
  confirmEach: { label: 'field.reads.rw29.confirm', detail: 'field.reads.rw29.confirmDetail', testID: 'set-confirm' },
  scanFirst: { label: 'field.reads.rw29.scanFirst', detail: 'field.reads.rw29.scanFirstDetail', testID: 'set-scan' },
};

/** One of the reading switches, as a row. */
export function ReadingSwitchRow({ which, divider }: { which: ReadingSwitch; divider?: boolean }) {
  const { t } = useTranslation();
  const { settings, setSettings } = useReads();
  const def = SWITCH[which];
  return (
    <ToggleRow
      divider={divider}
      label={t(def.label)}
      detail={t(def.detail)}
      value={settings[which]}
      onChange={(v) => setSettings({ ...settings, [which]: v })}
      testID={def.testID}
    />
  );
}

export function ReadingSettings() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <KeypadCard />
      <OrderCard />
      <Card>
        {READING_SWITCHES.map((w, i) => (
          <ReadingSwitchRow key={w} which={w} divider={i > 0} />
        ))}
        {/* DEF-FLD-10640 — the ONE photo switch, the same as FF-51's. RW-29 had its
            own *Photos on mobile data*, saved and read by nothing. */}
        <PhotosWifiOnlyRow divider />
      </Card>
      <Button testID="door-FF-51" onPress={() => go('FF-51')}>
        {t('field.reads.rw29.more')}
      </Button>
    </ScreenBody>
  );
}
