/**
 * FF-52 Notifications (T-25; US-FLD-013, -033; image
 * `phone/FF-52-notifications.png`).
 *
 * One card per push kind, each with its own sound and channel (`N25`;
 * requirement 13): EMERGENCY (red, its sound and vibration), NEW JOB, SCHEDULE
 * CHANGE, DISPATCH MESSAGES (notify, and the badge on the tab), and OFF DUTY
 * (quiet outside my shift — *Emergencies still come through*).
 *
 * The choices are kept on the handset (`prefs.ts`) for the push wiring to read
 * when it lands (T-41). The sounds are fixed per kind — the drawing names them
 * (Klaxon, Chime) and offers no picker — and *Play* plays one, which needs
 * that same wiring (`T-41`); until then the press says it cannot.
 *
 * An emergency's SOUND cannot be turned off here: R28 says it must be
 * acknowledged, and a silent emergency cannot be. Its vibration can.
 *
 * Each kind's card is its own component (B14 rule 43): the tablet board
 * (FF-52 T) lists the kinds and shows one beside the list.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, Notice, ToggleRow } from '../../components';
import { useTheme } from '../../theme';
import { useHandsetPrefs } from './hooks';
import { MeScreen } from './MeScreen';
import { type NotifyKey, PREF, writeFlag } from './prefs';
import { useMeServices } from './services';

function SoundRow(props: { name: string; onPlay: () => void; testID: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3], minHeight: theme.touch.control }}>
      <View style={{ flexGrow: 1 }}>
        <AppText variant="body" weight="heavy">
          {t('field.ff52.sound')}
        </AppText>
        <AppText variant="label" tone="muted">
          {props.name}
        </AppText>
      </View>
      <Button size="sm" onPress={props.onPlay} testID={props.testID} accessibilityLabel={`${t('field.ff52.play')} ${props.name}`}>
        {t('field.ff52.play')}
      </Button>
    </View>
  );
}

/** The kinds, in the board's order. */
export const NOTIFY_KINDS = ['emergency', 'newJob', 'schedule', 'dispatch', 'offDuty'] as const;
export type NotifyKind = (typeof NOTIFY_KINDS)[number];

/** What every card reads and writes: the choices kept on the handset, *Play*, and the line when it cannot. */
export function useNotifySettings() {
  const { t } = useTranslation();
  const services = useMeServices();
  const [prefs, reread] = useHandsetPrefs();
  const [notice, setNotice] = useState<string | null>(null);
  function toggle(key: NotifyKey) {
    return (on: boolean) => {
      writeFlag(services.prefs, PREF.NOTIFY + key, on);
      reread();
    };
  }
  async function play(kind: 'emergency' | 'newJob') {
    setNotice(null);
    try {
      await services.sounds.play(kind);
    } catch {
      setNotice(t('field.ff52.cannotPlay'));
    }
  }
  return { prefs, toggle, play, notice };
}

type NotifySettings = ReturnType<typeof useNotifySettings>;

/** One kind's card. */
export function NotifyKindCard({ kind, n }: { kind: NotifyKind; n: NotifySettings }) {
  const { t } = useTranslation();
  const { prefs, toggle, play } = n;
  switch (kind) {
    case 'emergency':
      return (
        <Card tone="danger" title={t('field.ff42.kind.emergency')} testID="ff52-emergency">
          <SoundRow name={t('field.ff52.klaxon')} onPlay={() => play('emergency')} testID="ff52-play-emergency" />
          <ToggleRow divider label={t('field.ff52.vibrate')} value={prefs.notify.emergencyVibrate} onChange={toggle('emergencyVibrate')} testID="ff52-emergency-vibrate" />
        </Card>
      );
    case 'newJob':
      return (
        <Card title={t('field.ff52.newJob')}>
          <SoundRow name={t('field.ff52.chime')} onPlay={() => play('newJob')} testID="ff52-play-new-job" />
          <ToggleRow divider label={t('field.ff52.vibrate')} value={prefs.notify.newJobVibrate} onChange={toggle('newJobVibrate')} testID="ff52-new-job-vibrate" />
        </Card>
      );
    case 'schedule':
      return (
        <Card title={t('field.ff42.kind.schedule')}>
          <ToggleRow label={t('field.ff52.notifyMe')} value={prefs.notify.scheduleChange} onChange={toggle('scheduleChange')} testID="ff52-schedule" />
        </Card>
      );
    case 'dispatch':
      return (
        <Card title={t('field.ff52.dispatchMessages')}>
          <ToggleRow label={t('field.ff52.notifyMe')} value={prefs.notify.dispatchMessages} onChange={toggle('dispatchMessages')} testID="ff52-dispatch" />
          <ToggleRow divider label={t('field.ff52.badge')} value={prefs.notify.dispatchBadge} onChange={toggle('dispatchBadge')} testID="ff52-badge" />
        </Card>
      );
    case 'offDuty':
      return (
        <Card title={t('field.ff52.offDuty')}>
          <ToggleRow
            label={t('field.ff52.quiet')}
            detail={t('field.ff52.quietDetail')}
            value={prefs.notify.quietOffShift}
            onChange={toggle('quietOffShift')}
            testID="ff52-quiet"
          />
        </Card>
      );
  }
}

export function NotificationsScreen() {
  const { t } = useTranslation();
  const n = useNotifySettings();
  return (
    <MeScreen id="FF-52" title={t('field.screen.ff52')} leading={{ back: 'FF-51' }}>
      {n.notice ? <Notice tone="warning">{n.notice}</Notice> : null}
      {NOTIFY_KINDS.map((kind) => (
        <NotifyKindCard key={kind} kind={kind} n={n} />
      ))}
    </MeScreen>
  );
}
