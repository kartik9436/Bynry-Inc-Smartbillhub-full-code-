/**
 * FF-44 Profile (T-24; US-FLD-006; image `phone/FF-44-profile.png`).
 *
 * Who is signed in, their availability (opens FF-45), today in three figures
 * (done · left · worked, from the handset's own orders and clocks), the
 * details card, and the rows the drawing draws: *Shifts and time off* (FF-46),
 * *Timesheet* (FF-47), *Settings* (FF-51).
 *
 * The details the handset does not hold — utility name, mobile,
 * certifications — come from a server door that does not exist yet
 * (`ME-profile`); a row whose fact is not known is left out rather than
 * filled with a guess. *Change photo* is not drawn here: nothing on the
 * handset takes or loads a profile photo yet (reported).
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Avatar, Card, Dot, ListRow, SyncChip } from '../../components';
import { useTheme } from '../../theme';
import { AVAILABILITY_TONE, useAvailability } from './availability';
import { formatClock, formatDuration } from './format';
import { useActiveTechnician, useHandsetPrefs, usePortRead } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { employmentWord } from '../onSite/job';
import { useMeServices } from './services';

const AVAILABILITY_KEY = {
  available: 'field.availability.available',
  onBreak: 'field.availability.onBreak',
  offDuty: 'field.availability.offDuty',
  unavailable: 'field.availability.unavailable',
} as const;

function Figure({ value, label, testID }: { value: string; label: string; testID?: string }) {
  return (
    <View style={{ flexGrow: 1, flexBasis: 0 }} accessible accessibilityLabel={`${value} ${label}`} testID={testID}>
      <AppText variant="title">{value}</AppText>
      <AppText variant="label" tone="muted">
        {label}
      </AppText>
    </View>
  );
}

export function ProfileScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-44');
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [availability] = useAvailability(tech?.technicianId ?? null);
  const [facts] = usePortRead(
    () => (tech ? services.profile.facts(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const today = tech ? services.data.today(tech.technicianId, services.now()) : null;
  const counts = tech ? services.data.syncCounts(tech.technicianId) : null;
  const fromServer = facts.state === 'ready' ? facts.value : null;
  // The handset's roster answers role and employment; the server door (`ME-profile`) the rest.
  const who = tech ? services.data.who(tech.technicianId) : null;
  const known = {
    role: fromServer?.role ?? who?.role ?? null,
    employment: fromServer?.employment ?? who?.employment ?? null,
    utility: fromServer?.utility ?? null,
    mobile: fromServer?.mobile ?? null,
    certificationsCurrent: fromServer?.certificationsCurrent ?? null,
  };

  const details: Array<[string, string]> = [];
  if (known.utility) details.push([t('field.ff44.utility'), known.utility]);
  // FB-023 F3: the roster holds the server's code; say it in words.
  if (known.employment) details.push([t('field.ff44.employment'), employmentWord(t, known.employment)]);
  if (known.mobile) details.push([t('field.ff44.mobile'), known.mobile]);
  if (known.certificationsCurrent != null)
    details.push([t('field.ff44.certifications'), t('field.ff44.certificationsCurrent', { count: known.certificationsCurrent })]);

  const availabilityLabel = availability.value ? t(AVAILABILITY_KEY[availability.value]) : t('field.availability.unknown');
  const sinceLabel =
    (availability.value === 'available' || availability.value === 'onBreak') && availability.since
      ? t('field.ff44.onDutySince', { time: formatClock(availability.since, prefs.clock) })
      : undefined;

  return (
    <MeScreen
      id="FF-44"
      title={t('field.screen.ff44')}
      leading="drawer"
      trailing={
        <SyncChip
          count={counts?.itemsWaiting ?? null}
          suffix={t('field.me.toSend')}
          accessibilityLabel={t('field.me.toSendA11y', { count: counts?.itemsWaiting ?? 0 })}
          onPress={() => door('FF-50')}
          testID="door-FF-50"
        />
      }
    >
      <Card>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[4] }}>
          <Avatar name={tech?.name ?? ''} size="large" />
          <View style={{ flexShrink: 1 }}>
            <AppText variant="title" testID="ff44-name">
              {tech?.name ?? ''}
            </AppText>
            {known.role ? (
              <AppText variant="body" tone="muted">
                {known.role}
              </AppText>
            ) : null}
          </View>
        </View>
      </Card>
      <Card>
        <ListRow
          leading={availability.value ? <Dot tone={AVAILABILITY_TONE[availability.value]} /> : undefined}
          label={availabilityLabel}
          detail={sinceLabel}
          onPress={() => door('FF-45')}
          testID="door-FF-45"
        />
      </Card>
      <Card title={t('field.ff44.today')}>
        {today ? (
          <View style={{ flexDirection: 'row', gap: theme.space[3] }}>
            <Figure value={String(today.done)} label={t('field.ff44.done')} testID="ff44-done" />
            <Figure value={String(today.left)} label={t('field.ff44.left')} testID="ff44-left" />
            <Figure value={formatDuration(today.workedMinutes)} label={t('field.ff44.worked')} testID="ff44-worked" />
          </View>
        ) : (
          <AppText variant="body" tone="muted">
            {t('field.me.notHereYet')}
          </AppText>
        )}
      </Card>
      {details.length > 0 ? (
        <Card title={t('field.ff44.details')} testID="ff44-details">
          {details.map(([label, value], i) => (
            <ListRow key={label} label={label} value={value} divider={i > 0} />
          ))}
        </Card>
      ) : null}
      <Card>
        <ListRow label={t('field.ff44.shifts')} onPress={() => door('FF-46')} testID="door-FF-46" />
        <ListRow divider label={t('field.nav.item.timesheet')} onPress={() => door('FF-47')} testID="door-FF-47" />
        <ListRow divider label={t('field.nav.item.settings')} onPress={() => door('FF-51')} testID="door-FF-51" />
      </Card>
    </MeScreen>
  );
}
