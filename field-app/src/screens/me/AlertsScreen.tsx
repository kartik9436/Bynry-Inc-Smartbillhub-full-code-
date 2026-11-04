/**
 * FF-42 Alerts (T-23; US-FLD-013; image `phone/FF-42-alerts.png`).
 *
 * Emergencies first and in red, with the clock to dispatch being told (R28);
 * then the other kinds, newest first, each with its kind and time: job
 * cancelled, payment cleared (R19 — read only, R16), schedule change, a
 * dispatch message with its author. Dispatch messages only — there is no crew
 * chat and no reply box (R29).
 *
 * The feed is a server door that does not exist yet (`N25`): until it does the
 * list says it has nothing on this phone, and *Mark read* says it did not
 * reach the server.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText, Button, Card, Dot, EmptyState, Kicker, ListRow, Notice } from '../../components';
import { useTheme } from '../../theme';
import type { StatusTone } from '../../theme';
import { firstOpenEmergency, isOpenEmergency, msUntilDispatchTold, useTicking } from './emergency';
import { formatClock, formatCountdown } from './format';
import { useActiveTechnician, useHandsetPrefs, usePortRead } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { type AlertItem, type AlertKind, useMeServices } from './services';

const KIND_KEY: Record<AlertKind, string> = {
  emergency: 'field.ff42.kind.emergency',
  urgent: 'field.ff42.kind.urgent',
  jobCancelled: 'field.ff42.kind.jobCancelled',
  paymentCleared: 'field.ff42.kind.paymentCleared',
  schedule: 'field.ff42.kind.schedule',
  dispatch: 'field.ff42.kind.dispatch',
};

const KIND_TONE: Record<AlertKind, StatusTone> = {
  emergency: 'danger',
  urgent: 'danger',
  jobCancelled: 'success',
  paymentCleared: 'success',
  schedule: 'info',
  dispatch: 'neutral',
};

function AlertCard({ alert, clock }: { alert: AlertItem; clock: 'h24' | 'h12' }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Card testID={`alert-${alert.id}`} style={alert.read ? { backgroundColor: theme.colors.surface } : undefined}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        <Dot tone={KIND_TONE[alert.kind]} />
        <View style={{ flexGrow: 1 }}>
          <Kicker>{t(KIND_KEY[alert.kind])}</Kicker>
        </View>
        <AppText variant="label" tone="muted">
          {formatClock(alert.at, clock)}
        </AppText>
      </View>
      <AppText variant="section">{alert.title}</AppText>
      {alert.detail ? <AppText variant="body">{alert.detail}</AppText> : null}
      {alert.note ? (
        <AppText variant="label" tone="muted">
          {alert.note}
        </AppText>
      ) : null}
    </Card>
  );
}

export function AlertsScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-42');
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [loaded, reload] = usePortRead(
    () => (tech ? services.alerts.list(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const [notice, setNotice] = useState<string | null>(null);

  const alerts = loaded.state === 'ready' ? loaded.value : null;
  const emergency = firstOpenEmergency(alerts);
  const now = useTicking(services.now, emergency != null);
  const others = (alerts ?? []).filter((a) => !isOpenEmergency(a)).sort((a, b) => Date.parse(b.at) - Date.parse(a.at));

  async function markRead() {
    if (!tech) return;
    setNotice(null);
    try {
      await services.alerts.markAllRead(tech.technicianId);
      reload();
    } catch {
      setNotice(t('field.me.notSent'));
    }
  }

  const left = emergency ? msUntilDispatchTold(emergency, now) : 0;

  return (
    <MeScreen
      id="FF-42"
      title={t('field.screen.ff42')}
      leading="drawer"
      trailing={
        <Button size="sm" onPress={markRead} disabled={!alerts || alerts.length === 0} testID="ff42-mark-read">
          {t('field.ff42.markRead')}
        </Button>
      }
      footer={
        <Button grow onPress={() => door('FF-10')} testID="door-FF-10">
          {t('field.ff42.today')}
        </Button>
      }
    >
      {notice ? <Notice tone="warning">{notice}</Notice> : null}
      {emergency ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`${t('field.ff42.emergencyOpen')}. ${emergency.title}`}
          onPress={() => door('FF-43')}
          testID="door-FF-43"
          style={{ minHeight: theme.touch.control }}
        >
          <Card tone="danger" title={t('field.ff42.emergencyOpen')} testID="ff42-emergency">
            <AppText variant="section">{emergency.title}</AppText>
            {emergency.address ? <AppText variant="body">{emergency.address}</AppText> : null}
            <AppText variant="label" weight="heavy" tone="danger" testID="ff42-countdown">
              {left > 0
                ? t('field.ff42.dispatchToldIn', { time: formatCountdown(left) })
                : t('field.ff42.dispatchTold')}
            </AppText>
          </Card>
        </Pressable>
      ) : (
        <Card>
          <ListRow label={t('field.ff42.noEmergency')} onPress={() => door('FF-43')} testID="door-FF-43" />
        </Card>
      )}
      {loaded.state === 'ready' && alerts === null ? (
        <EmptyState title={t('field.me.notHereYet')} helper={t('field.ff42.emptyHelper')} testID="ff42-not-wired" />
      ) : null}
      {alerts !== null && others.length === 0 && !emergency ? (
        <EmptyState title={t('field.ff42.none')} helper={t('field.ff42.emptyHelper')} />
      ) : null}
      <View style={{ gap: theme.space[3] }}>
        {others.map((a) => (
          <AlertCard key={a.id} alert={a} clock={prefs.clock} />
        ))}
      </View>
    </MeScreen>
  );
}
