/**
 * Sync, Settings and Notifications on a tablet (T-29). Each phone screen is
 * one long column of cards, not a list of the things its board picks, so the
 * board's list is built (`PickList`) and the picked card — the PHONE's own
 * card component, never a copy — is shown beside it:
 *
 * FF-50 T *Sync* (`tablet/FF-50-T-sync.png`)
 *   LIST   — *Both directions*: what is waiting to send (items), the
 *            photographs, and — only while there are any — what the server
 *            refused. ⚠ The board's *Coming down* line has no count on the
 *            handset (the pull is not counted, `SyncCounts`); left out.
 *   DETAIL — *Download everything* (FF-08) and *Sync now*, the status card,
 *            then the picked direction's card.
 * FF-51 T *Settings* (`tablet/FF-51-T-settings.png`)
 *   LIST   — the phone's sections: Appearance, Language and formats, Nearby
 *            work, Reading, Notifications, Sync and data, Permissions, About,
 *            Sign out — each with what it is set to now where it has one.
 *   DETAIL — the section's card; the sections that open their own screen
 *            (Reading, Notifications, Permissions, Sign out) are its door.
 * FF-52 T *Notifications* (`tablet/FF-52-T-notifications.png`)
 *   LIST   — the five kinds, each with whether it is on.
 *   DETAIL — the kind's card: its sound and *Play*, its switches. The board's
 *            critical-alert paragraph is rationale and is not on screen
 *            (B14 rule 33).
 */
import { type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Button, Card, Notice } from '../../components';
import { useLanguage } from '../../i18n/I18nProvider';
import { versionLabel } from '../../release/build';
import { readPrefs } from '../../screens/me/prefs';
import { useMeServices } from '../../screens/me/services';
import { useDoor } from '../../screens/me/MeScreen';
import { NOTIFY_KINDS, type NotifyKind, NotifyKindCard, useNotifySettings } from '../../screens/me/NotificationsScreen';
import {
  AboutSection,
  DateTimeSection,
  LanguageSection,
  NearbySection,
  PhotosWifiOnlyRow,
  ScreenSection,
  THEME_KEY,
} from '../../screens/me/SettingsScreen';
import { AttentionCard, OwnersCard, PhotoLines, RefusedCard, SignInToSendCard, SyncStatusCard, useSyncState, WaitingCards } from '../../screens/me/SyncScreen';
import { useThemeMode } from '../../theme';
import { DetailCard, DetailPane } from '../DetailPane';
import { PickList } from '../Pickable';
import { usePick, useSelectedOr } from '../selection';

// ── FF-50 Sync ────────────────────────────────────────────────────────────

export function SyncDirections() {
  const { t } = useTranslation();
  // Reading the pick re-renders the list whenever the detail re-picks (after
  // a refusal is sent again), so its counts are read afresh.
  usePick();
  const sync = useSyncState();
  const c = sync.counts;
  const items = [
    { id: 'send', title: t('field.ff50.waitingToSend'), value: c ? String(c.itemsWaiting) : null },
    { id: 'photos', title: t('field.tablet.ff50.photographs'), value: c ? String(c.photosWaiting) : null },
    ...(sync.refused && sync.refused.length > 0
      ? [{ id: 'refused', title: t('field.tablet.ff50.refused'), value: String(sync.refused.length) }]
      : []),
  ];
  return (
    <View style={{ flex: 1 }} testID="screen-FF-50">
      <PickList kicker={t('field.tablet.ff50.both')} items={items} testID="sync-directions" />
    </View>
  );
}

export function SyncDetail() {
  const { t } = useTranslation();
  const door = useDoor('FF-50');
  const pick = usePick();
  const sync = useSyncState();
  const which = useSelectedOr('direction') ?? 'send';
  return (
    <DetailPane
      testID="sync-detail"
      acts={
        <>
          <Button grow variant="primary" onPress={() => door('FF-08')} testID="pane-FF-08">
            {t('field.ff50.downloadEverything')}
          </Button>
          <Button grow busy={sync.running} onPress={sync.syncNow} testID="sync-detail-now">
            {sync.running ? t('field.ff50.sending') : t('field.ff50.syncNow')}
          </Button>
        </>
      }
    >
      {sync.notice ? (
        <Notice tone="warning" testID="sync-detail-notice">
          {sync.notice}
        </Notice>
      ) : null}
      <SyncStatusCard sync={sync} />
      <SignInToSendCard sync={sync} />
      {which === 'send' ? <WaitingCards sync={sync} photos={false} /> : null}
      {/* FB-022: still waiting to send, and failing — said where the waiting work is. */}
      {which === 'send' ? <AttentionCard sync={sync} /> : null}
      {which === 'photos' ? (
        <Card title={t('field.tablet.ff50.photographs')}>
          <PhotoLines sync={sync} />
        </Card>
      ) : null}
      {/* Sent again: re-pick so the list beside it re-counts. */}
      {which === 'refused' ? <RefusedCard sync={sync} onResent={() => pick.active && pick.pick('send')} /> : null}
      <OwnersCard sync={sync} />
    </DetailPane>
  );
}

// ── FF-51 Settings ────────────────────────────────────────────────────────

type Section = 'screen' | 'language' | 'nearby' | 'reading' | 'notifications' | 'sync' | 'permissions' | 'about' | 'signOut';

export function SettingsSections() {
  const { t } = useTranslation();
  const { mode } = useThemeMode();
  const { language, languages } = useLanguage();
  // Read on every render, and re-rendered on every pick (`usePick`), so a
  // choice made beside the list shows here the next time anything is picked.
  usePick();
  const prefs = readPrefs(useMeServices().prefs);
  const items: Array<{ id: Section; title: string; value?: string | null }> = [
    { id: 'screen', title: t('field.tablet.ff51.appearance'), value: t(THEME_KEY[mode]) },
    { id: 'language', title: t('field.tablet.ff51.language'), value: languages.find((l) => l.code === language)?.name ?? null },
    { id: 'nearby', title: t('field.ff51.nearby'), value: t('field.ff51.miles', { count: Number(prefs.nearbyRadius) }) },
    { id: 'reading', title: t('field.ff51.reading') },
    { id: 'notifications', title: t('field.ff51.notifications') },
    { id: 'sync', title: t('field.ff51.syncAndData'), value: prefs.photosWifiOnly ? t('field.tablet.on') : t('field.tablet.off') },
    { id: 'permissions', title: t('field.ff51.permissions') },
    { id: 'about', title: t('field.ff51.about'), value: versionLabel(t) },
    { id: 'signOut', title: t('field.nav.signOut') },
  ];
  return (
    <View style={{ flex: 1 }} testID="screen-FF-51">
      <PickList kicker={t('field.screen.ff51')} items={items} testID="settings-sections" />
    </View>
  );
}

/** A section that is a door to its own screen: its name and the way in. */
function DoorSection(props: { title: string; to: 'RW-29' | 'FF-52' | 'FF-07' | 'FF-53'; label: string; children?: ReactNode }) {
  const door = useDoor('FF-51');
  return (
    <DetailCard title={props.title} testID="settings-detail-card">
      {props.children}
      <Button onPress={() => door(props.to)} testID={`pane-${props.to}`}>
        {props.label}
      </Button>
    </DetailCard>
  );
}

export function SettingsDetail() {
  const { t } = useTranslation();
  const door = useDoor('FF-51');
  const which = (useSelectedOr('section') ?? 'screen') as Section;
  let body;
  switch (which) {
    case 'screen':
      body = <ScreenSection />;
      break;
    case 'language':
      body = (
        <>
          <LanguageSection />
          <DateTimeSection />
        </>
      );
      break;
    case 'nearby':
      body = <NearbySection />;
      break;
    case 'reading':
      body = <DoorSection title={t('field.ff51.reading')} to="RW-29" label={t('field.tablet.ff51.open')} />;
      break;
    case 'notifications':
      body = <DoorSection title={t('field.ff51.notifications')} to="FF-52" label={t('field.tablet.ff51.open')} />;
      break;
    case 'sync':
      body = (
        <DetailCard title={t('field.ff51.syncAndData')} testID="settings-detail-card">
          <PhotosWifiOnlyRow />
          <Button onPress={() => door('FF-50')} testID="pane-FF-50">
            {t('field.tablet.ff51.open')}
          </Button>
        </DetailCard>
      );
      break;
    case 'permissions':
      body = <DoorSection title={t('field.ff51.permissions')} to="FF-07" label={t('field.tablet.ff51.open')} />;
      break;
    case 'about':
      body = <AboutSection />;
      break;
    case 'signOut':
      body = <DoorSection title={t('field.nav.signOut')} to="FF-53" label={t('field.nav.signOut')} />;
      break;
  }
  return <DetailPane testID="settings-detail">{body}</DetailPane>;
}

// ── FF-52 Notifications ───────────────────────────────────────────────────

const KIND_TITLE: Record<NotifyKind, string> = {
  emergency: 'field.ff42.kind.emergency',
  newJob: 'field.ff52.newJob',
  schedule: 'field.ff42.kind.schedule',
  dispatch: 'field.ff52.dispatchMessages',
  offDuty: 'field.ff52.offDuty',
};

export function NotifyKinds() {
  const { t } = useTranslation();
  // The detail re-picks after a switch; reading the pick re-renders this list,
  // and the choices are read afresh from the handset each time.
  usePick();
  const n = { prefs: readPrefs(useMeServices().prefs) };
  const on = (v: boolean) => (v ? t('field.tablet.on') : t('field.tablet.off'));
  const value: Record<NotifyKind, string> = {
    // An emergency always sounds (R28); only its vibration is a choice.
    emergency: t('field.tablet.ff52.always'),
    newJob: on(n.prefs.notify.newJobVibrate),
    schedule: on(n.prefs.notify.scheduleChange),
    dispatch: on(n.prefs.notify.dispatchMessages),
    offDuty: on(n.prefs.notify.quietOffShift),
  };
  return (
    <View style={{ flex: 1 }} testID="screen-FF-52">
      <PickList
        kicker={t('field.screen.ff52')}
        items={NOTIFY_KINDS.map((k) => ({ id: k, title: t(KIND_TITLE[k]), value: value[k] }))}
        testID="notify-kinds"
      />
    </View>
  );
}

export function NotifyDetail() {
  const pick = usePick();
  const n = useNotifySettings();
  const kind = ((useSelectedOr('kind') ?? 'emergency') as NotifyKind) ?? 'emergency';
  return (
    <DetailPane testID="notify-detail">
      {n.notice ? (
        <Notice tone="warning" testID="notify-detail-notice">
          {n.notice}
        </Notice>
      ) : null}
      <NotifyKindCard
        kind={kind}
        n={{
          ...n,
          // A switch changed beside the list: re-pick so the list re-reads it.
          toggle: (key) => (on) => {
            n.toggle(key)(on);
            if (pick.active) pick.pick(kind);
          },
        }}
      />
    </DetailPane>
  );
}
