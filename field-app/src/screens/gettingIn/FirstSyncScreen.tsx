/**
 * FF-08 First sync — *Loading your day* (T-15; US-FLD-002 TC-1). Built from
 * `wireframes/phone/FF-08-first-sync.png` and its tablet board: *Wait for
 * 100% before you drive out.*, the big percentage, the bar, *3 of 11 jobs
 * still to come*, the five parts each with its own state, the connection
 * line, and *Skip · Open my day* — *Open my day* waits for 100%.
 *
 * The loader is `FieldData.firstSync` (`firstSync.ts`). With none wired the
 * screen says the day cannot load yet and leaves *Skip* — never a moving bar
 * over nothing. A part with no server feed says *Not available* on its own
 * row and is left out of the percentage, so 100% is reachable and true.
 *
 * Leaving this screen for the day RESETS the stack onto the frame, so back
 * from Today never returns to a loading screen.
 *
 * WHEN SOMETHING DID NOT LOAD (DEF-FLD-10608, decision log 2026-10-26
 * FA-10): the reason in words under the parts (*No signal.* · *Signed out.
 * Sign in again.* · *Server error.*), a **Retry** that re-runs only the failed
 * part, and *Some jobs are not on the phone.* above Skip. A job whose details
 * did not arrive is a warning (*10 of 11*), not a block — the day still
 * reaches 100%. *Open my day* stays a button; nothing moves on by itself.
 * FF-50's *Download everything* opens this same screen, so it shows the same.
 *
 * The board's *"About 40 seconds"* needs a size and a speed nobody measures
 * yet; the connection line states only what is known (online · offline).
 */
import { CommonActions, useNavigation } from '@react-navigation/native';
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, CheckRow, Figure, Notice, Page } from '../../components';
import type { CheckState } from '../../components';
import { FRAME, SHELL, TABS } from '../../navigation/routing';
import { useShellStatus } from '../../navigation/ShellStatus';
import { useTheme } from '../../theme';
import { useFieldData } from '../theDay/fieldData';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import {
  FIRST_SYNC_PARTS,
  type FirstSyncPart,
  type FirstSyncReason,
  hasShortfall,
  type FirstSyncPartId,
  type FirstSyncProgress,
  isComplete,
  jobsToCome,
  percentOf,
  reasonOf,
} from './firstSync';

const REASON_KEY: Record<FirstSyncReason, string> = {
  noSignal: 'field.firstSync.reason.noSignal',
  signedOut: 'field.firstSync.reason.signedOut',
  server: 'field.firstSync.reason.server',
  update: 'field.firstSync.reason.update',
  certificate: 'field.firstSync.reason.certificate',
  outdated: 'field.firstSync.reason.outdated',
};

const PART_KEY: Record<FirstSyncPartId, string> = {
  shift: 'field.firstSync.part.shift',
  documents: 'field.firstSync.part.documents',
  jobs: 'field.firstSync.part.jobs',
  assets: 'field.firstSync.part.assets',
  customers: 'field.firstSync.part.customers',
};

const ROW_STATE: Record<FirstSyncPart['state'], CheckState> = {
  waiting: 'waiting',
  loading: 'active',
  done: 'done',
  failed: 'refused',
  unavailable: 'waiting',
};

const STATE_KEY: Record<FirstSyncPart['state'], string> = {
  waiting: 'field.firstSync.state.waiting',
  loading: 'field.firstSync.state.loading',
  done: 'field.firstSync.state.done',
  failed: 'field.firstSync.state.failed',
  unavailable: 'field.firstSync.state.unavailable',
};

const WAITING: FirstSyncProgress = {
  parts: FIRST_SYNC_PARTS.map((id) => ({ id, state: 'waiting', done: 0, total: null })),
};

function FirstSyncBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { firstSync } = useFieldData();
  const status = useShellStatus();
  const [progress, setProgress] = useState<FirstSyncProgress>(WAITING);
  const [running, setRunning] = useState(false);
  const live = useRef(true);

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const follow = useCallback((go: (onProgress: (p: FirstSyncProgress) => void) => Promise<FirstSyncProgress>) => {
    setRunning(true);
    void go((p) => {
      if (live.current) setProgress(p);
    }).finally(() => {
      if (live.current) setRunning(false);
    });
  }, []);

  useEffect(() => {
    live.current = true;
    if (firstSync) follow((on) => firstSync.run(on));
    return () => {
      live.current = false;
    };
  }, [firstSync, follow]);

  const retry = () => {
    if (!firstSync || running) return;
    follow((on) => (firstSync.retry ? firstSync.retry(on) : firstSync.run(on)));
  };

  const openDay = () =>
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: FRAME, params: { screen: SHELL, params: { screen: TABS, params: { screen: 'FF-10' } } } }],
      }),
    );

  const percent = percentOf(progress);
  const complete = isComplete(progress);
  const toCome = jobsToCome(progress);
  const short = !running && hasShortfall(progress);
  const reason = short ? reasonOf(progress) : null;

  return (
    <Page
      testID="screen-FF-08"
      footer={
        <>
          <Button onPress={openDay} testID="first-sync-skip">
            {t('field.firstSync.skip')}
          </Button>
          <Button variant="primary" grow disabled={!complete} onPress={openDay} testID="door-FF-10">
            {t('field.firstSync.openDay')}
          </Button>
        </>
      }
    >
      <View style={{ paddingVertical: theme.space[4] }}>
        <AppText variant="title">{t('field.firstSync.title')}</AppText>
        <AppText variant="body" tone="muted">
          {t('field.firstSync.wait')}
        </AppText>
      </View>
      {firstSync ? (
        <>
          <Figure value={t('field.firstSync.percent', { n: percent })} label={t('field.firstSync.loaded')} size="xl" testID="first-sync-percent" />
          <View
            accessibilityRole="progressbar"
            accessibilityValue={{ min: 0, max: 100, now: percent }}
            style={{ height: theme.space[3], backgroundColor: theme.colors.divider }}
            testID="first-sync-bar"
          >
            <View
              style={{
                width: `${percent}%`,
                height: theme.space[3],
                backgroundColor: complete ? theme.colors.status.success.rule : theme.colors.status.warning.rule,
              }}
            />
          </View>
          {toCome && toCome.left > 0 ? (
            <AppText variant="body" weight="semibold" style={{ textAlign: 'center', color: theme.colors.statusInk.warning }} testID="first-sync-to-come">
              {t('field.firstSync.toCome', { left: toCome.left, total: toCome.total })}
            </AppText>
          ) : null}
          <View style={{ gap: theme.space[1], paddingTop: theme.space[3] }}>
            {progress.parts.map((part) => (
              <CheckRow
                key={part.id}
                state={ROW_STATE[part.state]}
                label={t(PART_KEY[part.id])}
                stateLabel={t(STATE_KEY[part.state])}
                value={
                  // Loading, or settled short of the list (*10 of 11*, a warning).
                  part.total != null && (part.state === 'loading' || (part.state === 'done' && part.done < part.total))
                    ? t('field.firstSync.of', { done: part.done, total: part.total })
                    : t(STATE_KEY[part.state])
                }
                testID={`first-sync-${part.id}`}
              />
            ))}
          </View>
          {reason ? (
            <Notice tone="warning" testID="first-sync-reason">
              {t(REASON_KEY[reason])}
            </Notice>
          ) : null}
          {short ? (
            <Button onPress={retry} testID="first-sync-retry">
              {t('field.firstSync.retry')}
            </Button>
          ) : null}
        </>
      ) : (
        <Notice tone="warning" testID="first-sync-not-wired">
          {t('field.firstSync.notWired')}
        </Notice>
      )}
      <Notice tone={status.connection === 'online' ? 'success' : 'warning'} testID="first-sync-connection">
        {t(status.connection === 'online' ? 'field.firstSync.online' : status.connection === 'offline' ? 'field.firstSync.offline' : 'field.firstSync.connectionUnknown')}
      </Notice>
      {/* Said by Skip, last before the footer, only when something did not load. */}
      {short ? (
        <AppText variant="body" weight="semibold" style={{ color: theme.colors.statusInk.warning }} testID="first-sync-skip-warning">
          {t('field.firstSync.skipWarning')}
        </AppText>
      ) : null}
    </Page>
  );
}

export function FirstSyncScreen() {
  return (
    <ScreenBoundary screen="FF-08">
      <FirstSyncBody />
    </ScreenBoundary>
  );
}
