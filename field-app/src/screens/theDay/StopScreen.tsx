/**
 * FF-14 Stop — one stop, and the way there (T-17). Built from
 * `wireframes/phone/FF-14-stop.png` and `tablet/FF-14-T-the-stop.png`.
 *
 * As drawn: the map with the stop's pin above a panel holding *DISPATCHED ·
 * P1* (read *SCHEDULED · P1* — MQ-009, PO 2026-10-26; the state's word and
 * tone come from `jobStatus.ts`, the one list), *Stop 2 of 11*, the street (*22 Cedar Court*) and the town (*Austin,
 * TX 78704*), *Aaron Bruner · WO-4824*, *Disconnect — non-payment · 12:00–
 * 17:00*, the distance, and *Google Maps · Apple Maps · Open the job*.
 *
 * The two maps buttons hand the phone's maps app the STREET ADDRESS ONLY
 * (Security §5; `directions.ts`) — never the customer, the order or the
 * coordinates. *Arrive 12:28* and *26 min* need a route time from a routing
 * service the design does not name; they are not shown rather than guessed.
 * The straight-line miles are shown when the handset knows where it is.
 */
import { useNavigation, useRoute } from '@react-navigation/native';
import { useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, View } from 'react-native';

import { AppText, Button, EmptyState, Figure, Glyph, Page, StatusChip } from '../../components';
import { dayBounds, getJob, listDay, PAGE_SIZE } from '../../db/queries/day';
import { useShellStatus } from '../../navigation/ShellStatus';
import { useTheme } from '../../theme';
import { directionsUrl } from './directions';
import { addressForDirections, localityLine, miles, milesBetween, windowText } from './format';
import { useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';
import { priorityTone, statusLook } from './jobStatus';
import { markersFor } from './MapScreen';
import { ScreenBoundary } from './ScreenBoundary';
import { useAcceptance } from './useAcceptance';

function StopBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const jobId = (route.params as { jobId?: string } | undefined)?.jobId ?? null;
  const { now, location, MapView } = useFieldData();
  const status = useShellStatus();
  const s = useScoped();
  // DEF-FLD-10579: *Open the job* is a start — it accepts a job not yet accepted.
  const acceptance = useAcceptance();

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.screen.ff14') });
  }, [navigation, t]);

  const job = s && jobId ? getJob(s, jobId) : null;
  if (!s || !job) {
    return (
      <Page testID="screen-FF-14">
        <EmptyState
          title={t('field.stop.noStop')}
          helper={t('field.stop.noStopHelp')}
          ctaLabel={t('field.nav.item.today')}
          onCta={() => openScreen(navigation, 'FF-10')}
          testID="stop-none"
        />
      </Page>
    );
  }

  const day = listDay(s, { ...dayBounds(now(), 0), today: true, limit: PAGE_SIZE });
  const position = day.findIndex((j) => j.id === job.id) + 1;
  const look = statusLook(job.dispatchState);
  const address = addressForDirections(job);
  const here = location.current();
  const distance = here && job.lat != null && job.lng != null ? milesBetween(here, { lat: job.lat, lng: job.lng }) : null;
  const marker = markersFor([job], (_n, a) => t('field.map.stopLabel', { n: position || 1, address: a })).map((m) => ({
    ...m,
    label: String(position || 1),
  }));
  const open = (app: 'google' | 'apple') => {
    if (address) void Linking.openURL(directionsUrl(app, address));
  };

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="screen-FF-14">
      <View style={{ flex: 1 }}>
        <MapView markers={marker} selectedId={job.id} offline={status.connection === 'offline'} testID="stop-map" />
      </View>
      <Page scroll surface="card" contentStyle={{ flexGrow: 0 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
          {look.labelKey ? <StatusChip tone={look.tone}>{t(look.labelKey)}</StatusChip> : null}
          {job.priorityCode ? <StatusChip tone={priorityTone(job.priorityCode)}>{job.priorityCode}</StatusChip> : null}
          <View style={{ flexGrow: 1 }} />
          {position > 0 ? (
            <AppText variant="label" tone="muted" testID="stop-position">
              {t('field.stop.position', { n: position, total: day.length })}
            </AppText>
          ) : null}
        </View>
        <View>
          <AppText variant="title" testID="stop-address">
            {job.addressLine ?? job.number ?? ''}
          </AppText>
          {localityLine(job) ? <AppText variant="body">{localityLine(job)}</AppText> : null}
        </View>
        <View>
          <AppText variant="label" tone="muted">
            {[job.customerName, job.number].filter(Boolean).join(' · ')}
          </AppText>
          <AppText variant="label" tone="muted">
            {[job.type, windowText(job.windowStart, job.windowEnd)].filter(Boolean).join(' · ')}
          </AppText>
        </View>
        {distance != null ? (
          <View style={{ borderTopWidth: theme.borderWidth.divider, borderTopColor: theme.colors.divider, paddingTop: theme.space[3] }}>
            <Figure value={miles(distance)} label={t('field.unit.miles')} testID="stop-distance" />
          </View>
        ) : null}
        {address ? (
          <>
            <Button variant="primary" icon={<Glyph name="navigate" colour={theme.colors.actionText} />} onPress={() => open('google')} testID="stop-google">
              {t('field.stop.google')}
            </Button>
            <Button icon={<Glyph name="navigate" />} onPress={() => open('apple')} testID="stop-apple">
              {t('field.stop.apple')}
            </Button>
          </>
        ) : null}
        <Button
          onPress={() => {
            acceptance.start(job.id);
            openScreen(navigation, 'FF-15', { jobId: job.id });
          }}
          testID="door-FF-15"
        >
          {t('field.today.openJob')}
        </Button>
      </Page>
    </View>
  );
}

export function StopScreen() {
  return (
    <ScreenBoundary screen="FF-14">
      <StopBody />
    </ScreenBoundary>
  );
}
