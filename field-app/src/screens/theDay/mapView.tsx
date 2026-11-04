/**
 * The map behind FF-13 Map and FF-14 Stop, as a PORT (`MapViewProps`) with a
 * placeholder implementation.
 *
 * ⚠ **THE NATIVE BUILD DRAWS THE REAL MAP** (`device/native/EsriMapView.tsx`,
 * react-native-maps + Esri `UrlTile`, 2026-10-21); this placeholder is for tests
 * and previews. Before that: NO MAP PACKAGE WAS INSTALLED.
 * The design's map is Esri street tiles through the tenant's integration
 * policy (ADR-011, AD-06; `OQ-WRK-12787` CLOSED 2026-10-04 — *"Do not ask
 * about this again"*), the same public World Street Map the web's Assets and
 * Work maps draw (`07-frontend/src/features/integrations/basemap.ts`:
 * `server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/
 * tile/{z}/{y}/{x}`, attribution *Tiles © Esri*). Drawing tiles on a phone
 * needs a native map view; the usual one is `react-native-maps` with a
 * `UrlTile` layer on that template (no Google or Apple key needed for a tile
 * overlay). A real implementation of `MapViewProps` replaces
 * `PlaceholderMapView` through `FieldDataProvider` and no screen changes.
 *
 * WHAT THE PLACEHOLDER DOES, so the screens can be built and walked today:
 * it lays each marker out by its own coordinates inside the box (a straight
 * projection of the markers' bounding box — no streets, no tiles, no
 * attribution, because nothing is drawn from Esri) and every marker is a real
 * 48pt button that selects its stop. It says it is not a map, in three words.
 *
 * R31: the map needs a signal. `offline` draws the offline state instead of
 * markers; the screens keep the day listed beside it, so nothing is lost.
 */
import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import type { LayoutChangeEvent } from 'react-native';
import { useTranslation } from 'react-i18next';

import { AppText, Notice } from '../../components';
import { textStyle } from '../../components/AppText';
import { useTheme } from '../../theme';
import type { StatusTone } from '../../theme';

export interface MapMarker {
  id: string;
  /** The number drawn on the pin (its place in the day). */
  label: string;
  lat: number;
  lng: number;
  tone: StatusTone;
  /** "Stop 2, 22 Cedar Court". */
  accessibilityLabel: string;
}

export interface MapViewProps {
  markers: readonly MapMarker[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  /** R31 — no signal: draw the offline state, never a stale picture. */
  offline: boolean;
  testID?: string;
}

/** Where a marker lands inside a w × h box, from the markers' own extent. */
export function project(
  markers: readonly Pick<MapMarker, 'lat' | 'lng'>[],
  w: number,
  h: number,
  inset: number,
): Array<{ x: number; y: number }> {
  if (markers.length === 0) return [];
  const lats = markers.map((m) => m.lat);
  const lngs = markers.map((m) => m.lng);
  const [minLat, maxLat] = [Math.min(...lats), Math.max(...lats)];
  const [minLng, maxLng] = [Math.min(...lngs), Math.max(...lngs)];
  const spanLat = maxLat - minLat || 1;
  const spanLng = maxLng - minLng || 1;
  const usableW = Math.max(w - inset * 2, 0);
  const usableH = Math.max(h - inset * 2, 0);
  return markers.map((m) => ({
    x: inset + (maxLat === minLat && maxLng === minLng ? usableW / 2 : ((m.lng - minLng) / spanLng) * usableW),
    // North is up: the largest latitude sits at the top.
    y: inset + (maxLat === minLat && maxLng === minLng ? usableH / 2 : ((maxLat - m.lat) / spanLat) * usableH),
  }));
}

export function PlaceholderMapView(props: MapViewProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const c = theme.colors;
  const [size, setSize] = useState({ w: 0, h: 0 });
  const pin = theme.touch.control;
  const points = project(props.markers, size.w, size.h, pin / 2 + theme.space[2]);

  return (
    <View
      testID={props.testID}
      onLayout={(e: LayoutChangeEvent) => setSize({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}
      style={{ flex: 1, backgroundColor: c.surface, borderBottomWidth: theme.borderWidth.divider, borderBottomColor: c.border }}
    >
      {props.offline ? (
        <View style={{ flex: 1, justifyContent: 'center', padding: theme.space[4] }}>
          <Notice tone="warning" testID="map-offline">
            {t('field.map.offline')}
          </Notice>
        </View>
      ) : (
        <>
          <View style={{ position: 'absolute', top: theme.space[3], right: theme.space[3] }}>
            <AppText variant="micro" tone="muted" testID="map-placeholder-note">
              {t('field.map.notInstalled')}
            </AppText>
          </View>
          {props.markers.map((m, i) => {
            const at = points[i];
            if (!at) return null;
            const pair = c.status[m.tone];
            const selected = m.id === props.selectedId;
            return (
              <Pressable
                key={m.id}
                accessibilityRole="button"
                accessibilityLabel={m.accessibilityLabel}
                accessibilityState={{ selected }}
                onPress={() => props.onSelect?.(m.id)}
                testID={`map-marker-${m.id}`}
                style={{
                  position: 'absolute',
                  left: at.x - pin / 2,
                  top: at.y - pin / 2,
                  width: pin,
                  height: pin,
                  borderRadius: pin / 2,
                  alignItems: 'center',
                  justifyContent: 'center',
                  backgroundColor: theme.name === 'sunlight' ? pair.bg : pair.rule,
                  borderWidth: selected ? theme.borderWidth.rule : theme.borderWidth.emphasis,
                  borderColor: selected ? c.text : c.card,
                }}
              >
                <Text style={[textStyle(theme, 'body', 'heavy'), { color: c.card }]}>{m.label}</Text>
              </Pressable>
            );
          })}
        </>
      )}
    </View>
  );
}
