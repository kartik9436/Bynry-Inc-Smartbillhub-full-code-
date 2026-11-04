/**
 * FF-11 Nearby — unassigned work near where the technician stands, sorted by
 * distance (T-16; US-FLD-023, -037). Built from `wireframes/phone/FF-11-
 * nearby.png` and `tablet/FF-11-T-nearby.png`.
 *
 * R2: a DIFFERENT list with a different question — it never touches Today's
 * order, and Today is never sorted by distance. The order here is the
 * server's distance order and is kept as it arrives.
 *
 * As drawn: *Mine · Nearby* (Mine goes back to Today), *Within 2 miles ▾*
 * with *3 unassigned* beside it, then one card per job — the distance as the
 * big figure, the priority, the address, *WO-4840 · Routine read*, *Due 22 Oct
 * · 10 min*, and *Claim*. A job someone took is drawn dimmed with *Taken by
 * R. Patel* and no button.
 *
 * R34: the radius is a setting, default 2 miles — the chip opens 1 · 2 · 5 ·
 * 10. The other filters R44 declares for Nearby (job type, priority, due
 * date) are not drawn on the board and are NOT built; the server route that
 * would answer them does not exist either (`nearbyApi.ts`).
 *
 * The data is the server's (N11, not built yet — `NearbyGapError`): the screen
 * says so in place of the list, never an empty radius.
 *
 * DEF-FLD-10605 (MQ-051): a load that fails says WHICH thing is missing —
 * *Location is off* with *Turn on location*, *Nearby needs a signal.*, or
 * *Could not load* from the server — each with its own way back. The tablet's
 * FF-11 T list is this screen (`tablet/layouts/NearbyLayout.tsx`).
 */
import { useNavigation, useRoute } from '@react-navigation/native';
import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { AppText, Button, ChoiceChips, EmptyState, Figure, Glyph, SegmentTabs, Sheet, StatusChip } from '../../components';
import { textStyle } from '../../components/AppText';
import { TransportError } from '../../sync/transport';
import { useGettingIn } from '../gettingIn/gettingInServices';
import { Pickable } from '../../tablet/Pickable';
import { useDefaultSelection, usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { estimate, miles, shortDate } from './format';
import { useFieldData } from './fieldData';
import { openScreen } from './go';
import { HeaderBell } from './HeaderBell';
import { HeaderMenu } from './HeaderMenu';
import { priorityTone } from './jobStatus';
import { DEFAULT_RADIUS_MI, type NearbyJob, NearbyGapError, NearbyNoFixError, RADIUS_CHOICES_MI, type RadiusMi } from './nearbyApi';
import { ScreenBoundary } from './ScreenBoundary';

type Load =
  | { state: 'loading' }
  | { state: 'ready'; jobs: NearbyJob[]; count: number; hasMore: boolean; page: number }
  | { state: 'gap' }
  | { state: 'off' }
  | { state: 'offline' }
  | { state: 'failed' };

/**
 * Why a load failed, as three different answers (DEF-FLD-10605, MQ-051) —
 * every one of them once read *Nearby needs a signal.*, which sent a
 * technician standing in full signal to look for one:
 *   off      the handset does not know where it is (no permission, no fix)
 *   offline  the request never reached the server (no `status`: no answer)
 *   failed   the server answered and could not (a 5xx is `network` WITH a status)
 */
export function nearbyFailure(err: unknown): 'gap' | 'off' | 'offline' | 'failed' {
  if (err instanceof NearbyGapError) return 'gap';
  if (err instanceof NearbyNoFixError) return 'off';
  if (err instanceof TransportError && err.kind === 'network' && err.status === undefined) return 'offline';
  return 'failed';
}

function NearbyCard({ job, onClaim }: { job: NearbyJob; onClaim: () => void }) {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  // FF-11 T / FF-12 T: beside the job, the card's body picks it (the job rides
  // with the pick — it is the server's, not on the handset) and is ruled heavy.
  const pick = usePick();
  const picked = pick.isPicked(job.id);
  const taken = job.takenBy != null;
  const numberLine = [job.number, job.type].filter(Boolean).join(' · ');
  const due = shortDate(job.dueAt, i18n.language);
  const dueLine = [due ? t('field.nearby.due', { date: due }) : null, estimate(t, job.estMinutes)].filter(Boolean).join(' · ');
  return (
    <View
      testID={`nearby-${job.id}`}
      style={{
        backgroundColor: taken ? theme.colors.surface : theme.colors.card,
        borderColor: picked ? theme.colors.text : theme.colors.border,
        borderWidth: picked ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
        padding: theme.space[4],
        gap: theme.space[1],
      }}
    >
      <Pickable id={job.id} payload={job} bare label={[job.address, numberLine].filter(Boolean).join(', ')} testID={`nearby-${job.id}-pick`}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
          <View style={{ flexGrow: 1 }}>
            {job.distanceMi != null ? (
              <Figure value={miles(job.distanceMi)} label={t('field.unit.miles')} inline tone={taken ? 'muted' : 'default'} />
            ) : null}
          </View>
          {job.priorityCode ? <StatusChip tone={priorityTone(job.priorityCode)}>{job.priorityCode}</StatusChip> : null}
        </View>
        <AppText variant="section" tone={taken ? 'muted' : 'default'}>
          {job.address ?? job.number ?? ''}
        </AppText>
        {numberLine ? (
          <AppText variant="label" tone="muted">
            {numberLine}
          </AppText>
        ) : null}
      </Pickable>
      {taken ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
          <Glyph name="person" colour={theme.colors.textMuted} size={theme.type.body} />
          <AppText variant="label" tone="muted" testID={`nearby-${job.id}-taken`}>
            {t('field.nearby.takenBy', { name: job.takenBy })}
          </AppText>
        </View>
      ) : (
        <>
          {dueLine ? (
            <AppText variant="label" tone="muted">
              {dueLine}
            </AppText>
          ) : null}
          <Button variant="primary" onPress={onClaim} testID={`nearby-${job.id}-claim`} style={{ marginTop: theme.space[3] }}>
            {t('field.nearby.claim')}
          </Button>
        </>
      )}
    </View>
  );
}

function NearbyBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { nearby } = useFieldData();
  const { permissions } = useGettingIn();
  const [radius, setRadius] = useState<RadiusMi>(DEFAULT_RADIUS_MI);
  const [picking, setPicking] = useState(false);
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  // FF-11 T draws the first job picked beside the list; FF-12 T the one being claimed.
  const claiming = (useRoute().params as { job?: NearbyJob } | undefined)?.job ?? null;
  const firstJob = claiming ?? (load.state === 'ready' ? (load.jobs[0] ?? null) : null);
  useDefaultSelection(firstJob?.id ?? null, firstJob ?? undefined);

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.screen.ff10'), headerLeft: () => <HeaderMenu />, headerRight: () => <HeaderBell /> });
  }, [navigation, t]);

  const fetchPage = useCallback(
    async (page: number, previous: NearbyJob[]) => {
      try {
        const answer = await nearby.list({ radiusMi: radius, page });
        setLoad({ state: 'ready', jobs: [...previous, ...answer.jobs], count: answer.count, hasMore: answer.hasMore, page });
      } catch (err) {
        setLoad({ state: nearbyFailure(err) });
      }
    },
    [nearby, radius],
  );

  useEffect(() => {
    setLoad({ state: 'loading' });
    void fetchPage(1, []);
  }, [fetchPage]);

  const retry = useCallback(() => {
    setLoad({ state: 'loading' });
    void fetchPage(1, []);
  }, [fetchPage]);

  // *Turn on location*: ask the platform; where it will not ask again, the
  // app's settings are the only place left. Allowed (or already allowed with
  // no fix yet) → load again, which asks for a fresh fix.
  const turnOnLocation = useCallback(async () => {
    if ((await permissions.status('location')) !== 'granted') {
      if (!permissions.canRequest || (await permissions.blocked?.('location'))) {
        await permissions.openSettings().catch(() => undefined);
        return;
      }
      if ((await permissions.request('location')) !== 'granted') return;
    }
    retry();
  }, [permissions, retry]);

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="screen-FF-11">
      <SegmentTabs
        label={t('field.today.whose')}
        tabs={[
          { id: 'mine', label: t('field.today.mine'), testID: 'door-FF-10' },
          { id: 'nearby', label: t('field.today.nearby'), testID: 'tab-nearby' },
        ]}
        active="nearby"
        onSelect={(id) => {
          if (id === 'mine') openScreen(navigation, 'FF-10');
        }}
      />
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.space[3],
          paddingHorizontal: theme.space[4],
          paddingVertical: theme.space[2],
          backgroundColor: theme.colors.card,
          borderBottomWidth: theme.borderWidth.divider,
          borderBottomColor: theme.colors.border,
        }}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t('field.nearby.within', { miles: radius })}
          accessibilityHint={t('field.nearby.radiusHint')}
          onPress={() => setPicking(true)}
          testID="nearby-radius"
          style={{
            minHeight: theme.touch.control,
            paddingHorizontal: theme.space[4],
            flexDirection: 'row',
            alignItems: 'center',
            gap: theme.space[2],
            backgroundColor: theme.colors.status.info.bg,
            borderColor: theme.colors.status.info.rule,
            borderWidth: theme.borderWidth.control,
            borderRadius: theme.radius.md,
          }}
        >
          <Text style={[textStyle(theme, 'body', 'heavy'), { color: theme.colors.status.info.fg }]}>
            {t('field.nearby.within', { miles: radius })}
          </Text>
        </Pressable>
        <View style={{ flexGrow: 1 }} />
        {load.state === 'ready' ? (
          <AppText variant="label" tone="muted" testID="nearby-count">
            {t('field.nearby.unassigned', { count: load.count })}
          </AppText>
        ) : null}
      </View>
      <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
        {load.state === 'loading' ? (
          <AppText variant="body" tone="muted" testID="nearby-loading">
            {t('field.common.loading')}
          </AppText>
        ) : load.state === 'gap' ? (
          <EmptyState title={t('field.nearby.gapTitle')} helper={t('field.nearby.gapHelp')} testID="nearby-gap" />
        ) : load.state === 'off' ? (
          <EmptyState
            title={t('field.nearby.offTitle')}
            helper={t('field.nearby.offHelp')}
            ctaLabel={t('field.nearby.turnOn')}
            onCta={() => void turnOnLocation()}
            testID="nearby-off"
          />
        ) : load.state === 'offline' ? (
          <EmptyState
            title={t('field.nearby.failedTitle')}
            helper={t('field.nearby.failedHelp')}
            ctaLabel={t('field.common.tryAgain')}
            onCta={retry}
            testID="nearby-offline"
          />
        ) : load.state === 'failed' ? (
          <EmptyState
            title={t('field.nearby.failedTitle')}
            helper={t('field.nearby.serverHelp')}
            ctaLabel={t('field.common.tryAgain')}
            onCta={retry}
            testID="nearby-failed"
          />
        ) : load.jobs.length === 0 ? (
          <EmptyState title={t('field.nearby.noneTitle')} helper={t('field.nearby.noneHelp')} testID="nearby-none" />
        ) : (
          <>
            {load.jobs.map((job) => (
              <NearbyCard key={job.id} job={job} onClaim={() => openScreen(navigation, 'FF-12', { job })} />
            ))}
            {load.hasMore ? (
              <Button onPress={() => void fetchPage(load.page + 1, load.jobs)} testID="nearby-more">
                {t('field.list.showMore')}
              </Button>
            ) : null}
          </>
        )}
      </ScrollView>
      <Sheet
        visible={picking}
        onClose={() => setPicking(false)}
        title={t('field.nearby.radiusTitle')}
        closeLabel={t('field.common.close')}
        testID="nearby-radius-sheet"
      >
        <ChoiceChips
          label={t('field.nearby.radiusTitle')}
          segments={RADIUS_CHOICES_MI.map((m) => ({ id: String(m), label: t('field.nearby.miles', { miles: m }) }))}
          active={String(radius)}
          fill
          onSelect={(id) => {
            setRadius(Number(id) as RadiusMi);
            setPicking(false);
          }}
          testID="nearby-radius-choice"
        />
      </Sheet>
    </View>
  );
}

export function NearbyScreen() {
  return (
    <ScreenBoundary screen="FF-11">
      <NearbyBody />
    </ScreenBoundary>
  );
}
