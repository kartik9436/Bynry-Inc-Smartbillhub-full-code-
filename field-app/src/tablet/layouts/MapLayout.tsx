/**
 * FF-13 T *Stops beside the map* (T-28; image `tablet/FF-13-T-map.png`).
 *
 *   LIST   — *Stops*: today's jobs in the day's own order (R1), each a
 *            numbered disc in its state's colour, the street, and its state
 *            or window; the picked one is ruled heavy. At its foot
 *            *Navigate to stop 2* (the street handed to the phone's maps app,
 *            Security §5) and *Open the job*.
 *   DETAIL — the map, the legend, and the same stops as pins; a pin and a
 *            row pick the same stop (one selection, the frame's).
 *
 * Same reads and same map port as the phone's FF-13 (`theDay/MapScreen.tsx`:
 * `markersFor`, `Legend`, `FieldData.MapView`), so a stop with no point is not
 * guessed onto the map — it is still listed, and the list says how many are
 * off it. Paged like every list (NFR-3): *Show more* past the first page.
 * ⚠ *Open the job* is a door FF-13's phone board does not draw (it opens the
 * stop, FF-14); reported for the door table, test id `pane-FF-15`.
 */
import { type NavigationProp, type ParamListBase, useNavigation } from '@react-navigation/native';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, View } from 'react-native';

import { AppText, Button, EmptyState } from '../../components';
import { NumberDisc } from '../../components/NumberDisc';
import { dayBounds, type DayJob, listDay, PAGE_SIZE } from '../../db/queries/day';
import { useShellStatus } from '../../navigation/ShellStatus';
import { PressCard, Spread } from '../../screens/reads/parts';
import { directionsUrl } from '../../screens/theDay/directions';
import { useFieldData, useScoped } from '../../screens/theDay/fieldData';
import { addressForDirections, windowText } from '../../screens/theDay/format';
import { openScreen } from '../../screens/theDay/go';
import { statusLook } from '../../screens/theDay/jobStatus';
import { Legend, markersFor } from '../../screens/theDay/MapScreen';
import { useTheme } from '../../theme';
import { useTabletSelection } from '../TabletFrame';
import { useDefaultSelection } from '../selection';
import { PaneScreen } from './parts';

/** Today's stops, `pages` pages of them. */
function useStops(pages: number): DayJob[] {
  const { now } = useFieldData();
  const s = useScoped();
  return s ? listDay(s, { ...dayBounds(now(), 0), today: true, limit: PAGE_SIZE * pages }) : [];
}

export function StopsList() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const sel = useTabletSelection();
  const [pages, setPages] = useState(1);
  const stops = useStops(pages);
  const picked = stops.find((j) => j.id === sel.selected) ?? stops[0] ?? null;
  const n = picked ? stops.indexOf(picked) + 1 : 0;
  const address = picked ? addressForDirections(picked) : null;

  return (
    <PaneScreen
      title={t('field.tablet.ff13.stops')}
      testID="stops-pane"
      footer={
        picked ? (
          <View style={{ flex: 1, gap: theme.space[2] }}>
            <Button
              variant="primary"
              disabled={!address}
              onPress={() => (address ? void Linking.openURL(directionsUrl('google', address)) : undefined)}
              testID="stops-navigate"
            >
              {t('field.tablet.ff13.navigate', { n })}
            </Button>
            <Button onPress={() => openScreen(navigation, 'FF-15', { workOrderId: picked.id, jobId: picked.id })} testID="pane-FF-15">
              {t('field.tablet.ff13.openJob')}
            </Button>
          </View>
        ) : undefined
      }
    >
      {stops.length === 0 ? <EmptyState title={t('field.map.noStops')} helper={t('field.today.noJobsHelp')} testID="stops-none" /> : null}
      {stops.map((job, i) => {
        const look = statusLook(job.dispatchState);
        const line = [look.labelKey ? t(look.labelKey) : null, windowText(job.windowStart, job.windowEnd)].filter(Boolean).join(' · ');
        const street = job.addressLine ?? job.number ?? '';
        return (
          <PressCard
            key={job.id}
            label={t('field.map.stopLabel', { n: i + 1, address: street })}
            emphasis={job.id === picked?.id ? 'strong' : 'none'}
            onPress={() => sel.select(job.id)}
            testID={`stop-${job.id}`}
          >
            <Spread>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3], flexShrink: 1 }}>
                <NumberDisc n={i + 1} tone={look.tone} />
                <View style={{ flexShrink: 1 }}>
                  <AppText variant="body" weight="heavy">
                    {street}
                  </AppText>
                  {line ? (
                    <AppText variant="label" tone="muted">
                      {line}
                    </AppText>
                  ) : null}
                </View>
              </View>
            </Spread>
          </PressCard>
        );
      })}
      {stops.length === PAGE_SIZE * pages ? (
        <Button size="sm" onPress={() => setPages((p) => p + 1)} testID="stops-more">
          {t('field.list.showMore')}
        </Button>
      ) : null}
    </PaneScreen>
  );
}

export function StopsMap() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { MapView } = useFieldData();
  const status = useShellStatus();
  const sel = useTabletSelection();
  const stops = useStops(1);
  const markers = markersFor(stops, (n, address) => t('field.map.stopLabel', { n, address }));
  const offMap = stops.length - markers.length;
  const first = stops.find((j) => j.lat != null && j.lng != null) ?? stops[0] ?? null;
  useDefaultSelection(first?.id);
  const chosen = sel.selected ?? first?.id ?? null;
  return (
    // The board draws the map edge to edge, with no bar of its own.
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID="map-pane">
      <View style={{ flex: 1 }}>
        <MapView markers={markers} selectedId={chosen} onSelect={sel.select} offline={status.connection === 'offline'} testID="map" />
        {status.connection === 'offline' ? null : <Legend />}
      </View>
      {offMap > 0 ? (
        <View style={{ padding: theme.space[3], backgroundColor: theme.colors.card }}>
          <AppText variant="label" tone="muted" testID="map-off-map">
            {t('field.map.offMap', { count: offMap })}
          </AppText>
        </View>
      ) : null}
    </View>
  );
}
