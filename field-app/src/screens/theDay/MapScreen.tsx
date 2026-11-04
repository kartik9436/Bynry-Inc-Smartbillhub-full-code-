/**
 * FF-13 Map — today's stops on a street map (T-17; AD-06, ADR-011). Built
 * from `wireframes/phone/FF-13-map.png` and `tablet/FF-13-T-map.png`.
 *
 * As drawn: the header (menu, *Map*, the bell), the map with a numbered pin
 * per stop coloured by state and a legend (*In progress · Scheduled ·
 * Queued* — the drawing's *Dispatched* reads *Scheduled* by MQ-009, PO
 * 2026-10-26), and under it the chosen stop — its number, the address, *WO-4824
 * · 12:00–17:00* — which opens the stop (FF-14).
 *
 * The map is `FieldData.MapView` — a port, because no map package is
 * installed (`mapView.tsx` names the dependency). The pins are today's jobs in
 * the day's own order (R1), read from the handset; a job whose premises has
 * no point is not guessed onto the map — the screen counts it under the map
 * (*1 not on the map*), so a missing pin is never silent (law 7).
 *
 * R31: the map needs a signal. With the connection known to be offline the
 * map draws its offline state, and the stops stay listed below it.
 */
import { useNavigation } from '@react-navigation/native';
import { useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, EmptyState, ListRow, Page } from '../../components';
import { dayBounds, type DayJob, listDay, PAGE_SIZE } from '../../db/queries/day';
import { useShellStatus } from '../../navigation/ShellStatus';
import { useTheme } from '../../theme';
import { windowText } from './format';
import { useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';
import { HeaderBell } from './HeaderBell';
import { HeaderMenu } from './HeaderMenu';
import { LEGEND, statusLook } from './jobStatus';
import type { MapMarker } from './mapView';
import { ScreenBoundary } from './ScreenBoundary';

export function markersFor(jobs: readonly DayJob[], stopLabel: (n: number, address: string) => string): MapMarker[] {
  const out: MapMarker[] = [];
  jobs.forEach((job, i) => {
    if (job.lat == null || job.lng == null) return;
    out.push({
      id: job.id,
      label: String(i + 1),
      lat: job.lat,
      lng: job.lng,
      tone: statusLook(job.dispatchState).tone,
      accessibilityLabel: stopLabel(i + 1, job.addressLine ?? job.number ?? ''),
    });
  });
  return out;
}

export function Legend() {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <View
      testID="map-legend"
      style={{
        position: 'absolute',
        top: theme.space[3],
        left: theme.space[3],
        backgroundColor: theme.colors.card,
        borderColor: theme.colors.border,
        borderWidth: theme.borderWidth.card,
        borderRadius: theme.radius.md,
        padding: theme.space[3],
        gap: theme.space[1],
      }}
    >
      {LEGEND.map((l) => (
        <View key={l.key} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
          <View
            style={{
              width: theme.space[3],
              height: theme.space[3],
              borderRadius: theme.space[3] / 2,
              backgroundColor: theme.name === 'sunlight' ? theme.colors.status[l.tone].bg : theme.colors.status[l.tone].rule,
            }}
          />
          <AppText variant="label" weight="semibold">
            {t(l.labelKey)}
          </AppText>
        </View>
      ))}
    </View>
  );
}

function MapBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { now, MapView } = useFieldData();
  const status = useShellStatus();
  const s = useScoped();
  const [selected, setSelected] = useState<string | null>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.screen.ff13'), headerLeft: () => <HeaderMenu />, headerRight: () => <HeaderBell /> });
  }, [navigation, t]);

  if (!s) {
    return (
      <Page testID="screen-FF-13">
        <EmptyState title={t('field.today.notLoaded')} helper={t('field.today.notLoadedHelp')} testID="map-not-loaded" />
      </Page>
    );
  }

  const jobs = listDay(s, { ...dayBounds(now(), 0), today: true, limit: PAGE_SIZE });
  const markers = markersFor(jobs, (n, address) => t('field.map.stopLabel', { n, address }));
  const offMap = jobs.length - markers.length;
  const chosen = jobs.find((j) => j.id === selected) ?? jobs.find((j) => j.lat != null && j.lng != null) ?? jobs[0] ?? null;
  const chosenIndex = chosen ? jobs.indexOf(chosen) + 1 : 0;

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="screen-FF-13">
      <View style={{ flex: 1 }}>
        <MapView markers={markers} selectedId={chosen?.id ?? null} onSelect={setSelected} offline={status.connection === 'offline'} testID="map" />
        {status.connection === 'offline' ? null : <Legend />}
      </View>
      <View style={{ backgroundColor: theme.colors.card, paddingHorizontal: theme.space[4] }}>
        {chosen ? (
          <ListRow
            label={`${chosenIndex} · ${chosen.addressLine ?? chosen.number ?? ''}`}
            detail={[chosen.number, windowText(chosen.windowStart, chosen.windowEnd)].filter(Boolean).join(' · ')}
            onPress={() => openScreen(navigation, 'FF-14', { jobId: chosen.id })}
            testID="door-FF-14"
          />
        ) : (
          <AppText variant="body" tone="muted" testID="map-no-stops">
            {t('field.map.noStops')}
          </AppText>
        )}
        {offMap > 0 ? (
          <AppText variant="label" tone="muted" testID="map-off-map">
            {t('field.map.offMap', { count: offMap })}
          </AppText>
        ) : null}
        <View style={{ paddingBottom: theme.space[3] }}>
          <Button size="sm" onPress={() => openScreen(navigation, 'FF-10')} testID="door-FF-10">
            {t('field.nav.item.today')}
          </Button>
        </View>
      </View>
    </View>
  );
}

export function MapScreen() {
  return (
    <ScreenBoundary screen="FF-13">
      <MapBody />
    </ScreenBoundary>
  );
}
