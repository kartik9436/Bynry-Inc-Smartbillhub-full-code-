/**
 * FF-43 Emergency (T-23; US-FLD-013; image `phone/FF-43-emergency.png`).
 *
 * The whole screen in the danger ink: what, where, how far, what the caller
 * said, the clock to dispatch being told (R28), and three acts —
 *   *Acknowledge* — the one thing the screen is for (R28). It goes to the
 *     server's acknowledgement route (`N25`), which another lane is building;
 *     until it exists the press says it did not reach dispatch and the
 *     technician stays here, because an acknowledgement nobody received is
 *     not one.
 *   *Call dispatch* and *Cannot attend* — both are a CALL. R107 (PO ruled):
 *     *"An emergency cannot be handed back from the app. It takes a call to
 *     dispatch, so a person knows nobody is going."* So *Cannot attend* never
 *     hands the job back; it rings dispatch. The number is not on the handset
 *     yet (`ME-dispatch-phone`).
 *
 * Breaking silent mode on a locked iPhone needs Apple's Critical Alerts
 * entitlement — applied for (T-01) — and push itself is wired later; this
 * screen is what the alert opens onto.
 */
import { useNavigation } from '@react-navigation/native';
import { useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ScrollView, View } from 'react-native';

import {
  AlarmButton,
  AlarmCallout,
  AlarmPanel,
  AlarmSurface,
  AlarmText,
  AppText,
  Button,
  EmptyState,
} from '../../components';
import { useTheme } from '../../theme';
import { firstOpenEmergency, msUntilDispatchTold, useTicking } from './emergency';
import { formatClock, formatCountdown, formatDistance } from './format';
import { useActiveTechnician, useHandsetPrefs, usePortRead } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { useMeServices } from './services';

function FactRow({ label, value, divider }: { label: string; value: string; divider?: boolean }) {
  const theme = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${label}, ${value}`}
      style={{
        minHeight: theme.touch.control,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: theme.space[3],
        borderTopWidth: divider ? theme.borderWidth.divider : 0,
        borderTopColor: theme.colors.card,
      }}
    >
      <AlarmText>{label}</AlarmText>
      <AlarmText weight="heavy">{value}</AlarmText>
    </View>
  );
}

export function EmergencyScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const navigation = useNavigation();
  const door = useDoor('FF-43');
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [loaded] = usePortRead(
    () => (tech ? services.alerts.list(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const emergency = loaded.state === 'ready' ? firstOpenEmergency(loaded.value) : null;
  const now = useTicking(services.now, emergency != null);

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  if (!emergency) {
    return (
      <MeScreen id="FF-43" title={t('field.screen.ff43')}>
        <EmptyState title={t('field.ff43.none')} helper={t('field.ff43.noneHelper')} testID="ff43-none" />
        <Button onPress={() => door('FF-42')} testID="door-FF-42">
          {t('field.ff43.backToAlerts')}
        </Button>
      </MeScreen>
    );
  }

  async function acknowledge() {
    if (!tech || !emergency) return;
    setBusy(true);
    setProblem(null);
    try {
      await services.alerts.acknowledge(tech.technicianId, emergency.id, services.now());
      door('FF-42');
    } catch {
      setProblem(t('field.ff43.ackNotSent'));
    } finally {
      setBusy(false);
    }
  }

  async function callDispatch() {
    setProblem(null);
    try {
      await services.dispatch.call();
    } catch {
      setProblem(t('field.ff43.noDispatchNumber'));
    }
  }

  const left = msUntilDispatchTold(emergency, now);
  const distance =
    emergency.distanceMiles != null ? formatDistance(emergency.distanceMiles, prefs.units) : null;
  const reported = [emergency.reportedAt ? formatClock(emergency.reportedAt, prefs.clock) : null, emergency.reportedBy]
    .filter(Boolean)
    .join(' · ');

  return (
    <AlarmSurface testID="screen-FF-43">
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
        <View style={{ alignItems: 'center', gap: theme.space[2], paddingTop: theme.space[6] }}>
          <AlarmText variant="title" center>
            {'⚠'}
          </AlarmText>
          <AlarmText variant="micro" weight="heavy" kicker center>
            {emergency.priority ? `${t('field.ff42.kind.emergency')} · ${emergency.priority}` : t('field.ff42.kind.emergency')}
          </AlarmText>
          <AlarmText variant="title" center testID="ff43-title">
            {emergency.title}
          </AlarmText>
        </View>
        <AlarmPanel>
          {emergency.address ? (
            <AlarmText variant="section" testID="ff43-address">
              {emergency.address}
            </AlarmText>
          ) : null}
          {emergency.locality ? <AlarmText variant="label">{emergency.locality}</AlarmText> : null}
          {reported ? <FactRow divider label={t('field.ff43.reported')} value={reported} /> : null}
          {distance ? (
            <FactRow
              divider
              label={t('field.ff43.distance')}
              value={
                emergency.driveMinutes != null
                  ? t(distance.unit === 'km' ? 'field.ff43.distanceKmDrive' : 'field.ff43.distanceMilesDrive', {
                      value: distance.value,
                      minutes: emergency.driveMinutes,
                    })
                  : t(distance.unit === 'km' ? 'field.ff43.distanceKm' : 'field.ff43.distanceMiles', { value: distance.value })
              }
            />
          ) : null}
          {emergency.workOrderNumber ? (
            <FactRow divider label={t('field.ff43.order')} value={emergency.workOrderNumber} />
          ) : null}
        </AlarmPanel>
        {emergency.said ? (
          <AlarmPanel>
            <AlarmText variant="micro" weight="heavy" kicker>
              {t('field.ff43.said')}
            </AlarmText>
            <AlarmText>{emergency.said}</AlarmText>
          </AlarmPanel>
        ) : null}
        <AlarmCallout
          testID="ff43-countdown"
          label={left > 0 ? t('field.ff43.toldIn') : t('field.ff42.dispatchTold')}
          figure={left > 0 ? formatCountdown(left) : '0:00'}
        />
        {problem ? (
          <View accessibilityRole="alert" testID="ff43-problem" style={{ backgroundColor: theme.colors.card, padding: theme.space[3] }}>
            <AppText variant="body" weight="semibold" tone="danger">
              {problem}
            </AppText>
          </View>
        ) : null}
      </ScrollView>
      <View style={{ padding: theme.space[4], gap: theme.touch.clear }}>
        <AlarmButton variant="solid" onPress={acknowledge} disabled={busy} testID="door-FF-42">
          {t('field.ff43.acknowledge')}
        </AlarmButton>
        <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          <AlarmButton grow onPress={callDispatch} testID="ff43-call">
            {t('field.ff43.callDispatch')}
          </AlarmButton>
          <AlarmButton grow onPress={callDispatch} testID="ff43-cannot-attend">
            {t('field.ff43.cannotAttend')}
          </AlarmButton>
        </View>
      </View>
    </AlarmSurface>
  );
}
