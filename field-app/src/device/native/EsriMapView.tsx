/**
 * The REAL map behind FF-13 Map and FF-14 Stop (`MapViewProps`,
 * `screens/theDay/mapView.tsx`): `react-native-maps` with Esri's World Street
 * Map drawn as a `UrlTile` layer (ADR-011, AD-06; `OQ-WRK-12787` CLOSED —
 * *"Do not ask about this again"*). One map: the stops and nothing else — no
 * asset-network layer in v1.
 *
 * THE TILE HOST IS A PARAMETER, never written into a screen: the web reads it
 * from the tenant's integration policy (`GET /integrations/page-policy` →
 * `tile_host`, `07-frontend/src/features/integrations/basemap.ts`), and a null
 * host means the utility switched the basemap off — the stops are then drawn
 * over a plain ground, never over a host the policy does not permit. The app
 * root passes the host (`NativeApp.tsx`); reading it from the tenant's policy
 * on the handset is the follow-up named there.
 *
 * The platform's own map is hidden under the tiles (`mapType="none"` on
 * Android, `shouldReplaceMapContent` on iOS), so the streets are Esri's alone.
 * ⚠ ANDROID STILL NEEDS A GOOGLE MAPS SDK KEY to start the native map view at
 * all, even though no Google tile is drawn (`app.config.ts`,
 * `GOOGLE_MAPS_ANDROID_API_KEY`). iOS needs none.
 *
 * Attribution *Tiles © Esri* is Esri's requirement and is not translated.
 * R31: no signal → the offline state, never a stale picture.
 */
import { Platform, Pressable, Text, View } from 'react-native';
import MapView, { Marker, UrlTile } from 'react-native-maps';
import { useTranslation } from 'react-i18next';

import { AppText, Notice } from '../../components';
import { textStyle } from '../../components/AppText';
import type { MapMarker, MapViewProps } from '../../screens/theDay/mapView';
import { useTheme } from '../../theme';

export const ESRI_ATTRIBUTION = 'Tiles © Esri';
/** The path Esri's World Street Map serves tiles at, under any host (the web's `TILE_PATH`). */
export const TILE_PATH = '/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}';
/** Esri's public host — the shipped default the web draws too (B16 §10-D6). */
export const ESRI_PUBLIC_HOST = 'https://server.arcgisonline.com';
/** World Street Map's deepest level. */
export const MAX_ZOOM = 19;

export function tileUrlFor(host: string | null | undefined): string | null {
  const trimmed = (host ?? '').trim().replace(/\/+$/, '');
  return trimmed === '' ? null : `${trimmed}${TILE_PATH}`;
}

export interface Region {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}

/** The region that shows every marker with a margin; a single stop gets a street-level view. */
export function regionFor(markers: readonly Pick<MapMarker, 'lat' | 'lng'>[]): Region | undefined {
  if (markers.length === 0) return undefined;
  const lats = markers.map((m) => m.lat);
  const lngs = markers.map((m) => m.lng);
  const [minLat, maxLat, minLng, maxLng] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
  const street = 0.005;
  return {
    latitude: (minLat + maxLat) / 2,
    longitude: (minLng + maxLng) / 2,
    latitudeDelta: Math.max((maxLat - minLat) * 1.4, street),
    longitudeDelta: Math.max((maxLng - minLng) * 1.4, street),
  };
}

export function esriMapView(tileHost: string | null) {
  const urlTemplate = tileUrlFor(tileHost);

  return function EsriMapView(props: MapViewProps) {
    const theme = useTheme();
    const { t } = useTranslation();
    const c = theme.colors;
    const pin = theme.touch.control;

    if (props.offline) {
      return (
        <View testID={props.testID} style={{ flex: 1, justifyContent: 'center', padding: theme.space[4], backgroundColor: c.surface }}>
          <Notice tone="warning" testID="map-offline">
            {t('field.map.offline')}
          </Notice>
        </View>
      );
    }

    return (
      <View testID={props.testID} style={{ flex: 1, borderBottomWidth: theme.borderWidth.divider, borderBottomColor: c.border }}>
        <MapView
          style={{ flex: 1 }}
          initialRegion={regionFor(props.markers)}
          mapType={Platform.OS === 'android' ? 'none' : 'standard'}
          toolbarEnabled={false}
          showsPointsOfInterest={false}
          testID="esri-map"
        >
          {urlTemplate ? <UrlTile urlTemplate={urlTemplate} maximumZ={MAX_ZOOM} shouldReplaceMapContent zIndex={-1} /> : null}
          {props.markers.map((m) => {
            const selected = m.id === props.selectedId;
            const pair = c.status[m.tone];
            return (
              <Marker
                key={m.id}
                coordinate={{ latitude: m.lat, longitude: m.lng }}
                onPress={() => props.onSelect?.(m.id)}
                accessibilityLabel={m.accessibilityLabel}
                testID={`map-marker-${m.id}`}
                tracksViewChanges={false}
              >
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={m.accessibilityLabel}
                  accessibilityState={{ selected }}
                  onPress={() => props.onSelect?.(m.id)}
                  style={{
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
              </Marker>
            );
          })}
        </MapView>
        {urlTemplate ? (
          <View style={{ position: 'absolute', right: theme.space[2], bottom: theme.space[2], backgroundColor: c.card, paddingHorizontal: theme.space[1] }}>
            <AppText variant="micro" tone="muted" testID="map-attribution">
              {ESRI_ATTRIBUTION}
            </AppText>
          </View>
        ) : null}
      </View>
    );
  };
}
