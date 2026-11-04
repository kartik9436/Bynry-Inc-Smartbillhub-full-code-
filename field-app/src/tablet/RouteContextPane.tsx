/**
 * The route context pane (T-29) — ONE pane, beside every T3 reading screen
 * (RW-09, RW-10, RW-13, RW-15…RW-22, RW-25). Built from RW-09 T, which draws
 * it, and the RW-15 T / RW-17 T / RW-21 T boards, which repeat it:
 *
 *   ROUTE    — *Maple Heights* · *WLK-07 · Water · walk*
 *   PROGRESS — *136 of 151* and the bar
 *   WHERE    — the stop's street, *Stop 12 · 3 meters*
 *   *The walk* (RW-05) · *Progress* (RW-22) — and *The stop* (RW-06), the
 *   reading screens' way back to the stop they are at
 *
 * This is the block RW-09 used to draw inside its own content when the
 * WINDOW was a tablet (`reads/entry.tsx`, the `entry-context` column); it now
 * lives once, here, and RW-09 lays its keypad out in the pane it is given.
 * Same words (`field.reads.rw09.*`), same queries.
 *
 * Which route: the record the screen is about — `readId`, `stopId` or
 * `routeId` — resolved exactly as the reading screens resolve it
 * (`reads/records.ts`). No reading services, or nothing resolved → one line
 * saying there is no route on this phone.
 */
import { type NavigationProp, type ParamListBase, useIsFocused, useNavigation, useRoute } from '@react-navigation/native';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollView, View } from 'react-native';

import { AppText, Button, Card, Kicker, Notice, ProgressBar } from '../components';
import * as walkQ from '../db/queries/readsWalk';
import { type ScreenId } from '../navigation/screens';
import { type ReadsParams } from '../screens/reads/ReadsScreen';
import { resolveAll, routeName, streetOf } from '../screens/reads/records';
import { useOptionalReads } from '../screens/reads/services';
import { openScreen } from '../screens/theDay/go';
import { useTheme } from '../theme';

export function RouteContextPane() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const route = useRoute();
  const focused = useIsFocused();
  const reads = useOptionalReads();
  const params = (route.params ?? {}) as ReadsParams;
  const version = reads?.version ?? 0;
  const found = useMemo(() => {
    if (!reads) return null;
    const all = resolveAll(reads.s, params);
    return { ...all, tally: all.route ? walkQ.tally(reads.s, all.route.id) : null };
    // `version` and `focused` are re-read triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reads, params.readId, params.stopId, params.routeId, version, focused]);

  if (!found?.route) {
    return (
      <View style={{ padding: theme.space[4] }} testID="route-context-pane">
        <Notice tone="info" testID="route-context-none">
          {t('field.reads.common.noRoute')}
        </Notice>
      </View>
    );
  }
  const { route: r, stop, tally } = found;
  const go = (id: ScreenId) => openScreen(navigation, id, { routeId: r.id });
  const count = tally ? t('field.reads.common.nOfM', { n: tally.done, m: tally.total }) : '';

  return (
    <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }} testID="route-context-pane">
      <View>
        <Kicker>{t('field.reads.rw09.route')}</Kicker>
        <AppText variant="title" testID="route-context-name">
          {routeName(r)}
        </AppText>
        <AppText variant="label" tone="muted">
          {[r.code, r.service, r.read_type].filter(Boolean).join(' · ')}
        </AppText>
      </View>
      {tally ? (
        <Card testID="route-context-progress">
          <Kicker>{t('field.reads.rw09.progress')}</Kicker>
          <AppText variant="section">{count}</AppText>
          <ProgressBar done={tally.done} problem={tally.could_not} total={tally.total} label={count} />
        </Card>
      ) : null}
      {stop ? (
        <Card testID="route-context-where">
          <Kicker>{t('field.reads.rw09.where')}</Kicker>
          <AppText variant="body" weight="heavy">
            {streetOf(stop)}
          </AppText>
          <AppText variant="label" tone="muted">
            {t('field.reads.rw05.metersAtStop', { n: stop.meters, position: stop.walk_position })}
          </AppText>
          {/* RW-09's way back to its stop is drawn on the tablet pane (the reads
              sweep: *"back (drawn on the tablet pane)"*), so it lives here, with
              the stop it goes to. */}
          <Button size="sm" onPress={() => openScreen(navigation, 'RW-06', { stopId: stop.id })} testID="route-context-stop">
            {t('field.reads.common.theStop')}
          </Button>
        </Card>
      ) : null}
      <Button onPress={() => go('RW-05')} testID="route-context-walk">
        {t('field.reads.common.theWalk')}
      </Button>
      <Button onPress={() => go('RW-22')} testID="route-context-progress-door">
        {t('field.reads.rw05.progressLink')}
      </Button>
    </ScrollView>
  );
}
