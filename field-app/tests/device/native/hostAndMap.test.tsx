/**
 * The two drawn pieces, rendered with their native modules mocked: the device
 * host (viewfinder, scanner sheet, stamp compositor) and the Esri map behind
 * FF-13 / FF-14.
 */
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { captureRef } from 'react-native-view-shot';

import { expoCamera } from '../../../src/device/native/camera';
import { DeviceHost } from '../../../src/device/native/DeviceHost';
import { ESRI_ATTRIBUTION, esriMapView, regionFor, tileUrlFor } from '../../../src/device/native/EsriMapView';
import { DeviceHostController } from '../../../src/device/native/host';
import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { MemoryKeyValueStore } from '../../../src/security/prefs';
import { ThemeProvider } from '../../../src/theme';

function mount(ui: ReactElement) {
  return render(
    <ThemeProvider initialMode="light">
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={new MemoryKeyValueStore()}>
        {ui}
      </I18nProvider>
    </ThemeProvider>,
  );
}

// eslint-disable-next-line @typescript-eslint/no-require-imports
const cameraMock = (require('expo-camera') as { __mock: { takePictureAsync: jest.Mock } }).__mock;

describe('the device host', () => {
  test('a photo request opens the viewfinder; the shutter answers with the camera\'s file', async () => {
    const host = new DeviceHostController();
    mount(<DeviceHost host={host} />);
    let shot: Promise<unknown> = Promise.resolve();
    act(() => {
      shot = host.requestPhoto();
    });
    expect(await screen.findByTestId('device-viewfinder')).toBeTruthy();
    expect(screen.getByTestId('device-camera-shutter')).toHaveTextContent('Take the photo');
    fireEvent.press(screen.getByTestId('device-camera-shutter'));
    await expect(shot).resolves.toEqual({ uri: 'file:///camera/shot.jpg', width: 4032, height: 3024 });
    expect(cameraMock.takePictureAsync).toHaveBeenCalledWith(expect.objectContaining({ quality: 1 }));
    await act(async () => {});
    expect(screen.queryByTestId('device-viewfinder')).toBeNull();
  });

  test('with the camera shown inline (RW-14, DEF-FLD-10630) the shutter shoots from it and no viewfinder opens', async () => {
    const host = new DeviceHostController();
    const port = expoCamera(host);
    const Preview = port.Preview!;
    mount(
      <>
        <DeviceHost host={host} />
        <Preview />
      </>,
    );
    expect(await screen.findByTestId('device-camera-inline')).toBeTruthy();
    let shot: Promise<unknown> = Promise.resolve();
    await act(async () => {
      shot = port.takePhoto();
    });
    await expect(shot).resolves.toEqual({ uri: 'file:///camera/shot.jpg', width: 4032, height: 3024 });
    expect(screen.queryByTestId('device-viewfinder')).toBeNull();
  });

  test('Cancel backs out with no photo; there is no gallery button (R93)', async () => {
    const host = new DeviceHostController();
    mount(<DeviceHost host={host} />);
    let shot: Promise<unknown> = Promise.resolve();
    act(() => {
      shot = host.requestPhoto();
    });
    await screen.findByTestId('device-viewfinder');
    expect(screen.queryByText(/gallery|library/i)).toBeNull();
    fireEvent.press(screen.getByTestId('device-camera-cancel'));
    await expect(shot).resolves.toBeNull();
  });

  test('a scan with no inline preview gets the full-screen scanner; Close ends it', async () => {
    const host = new DeviceHostController();
    mount(<DeviceHost host={host} />);
    const onClose = jest.fn();
    act(() => {
      host.startScan(['qr'], () => undefined, onClose);
    });
    expect(await screen.findByTestId('device-scan-sheet')).toBeTruthy();
    fireEvent.press(screen.getByTestId('device-scan-close'));
    expect(onClose).toHaveBeenCalled();
    await act(async () => {});
    expect(screen.queryByTestId('device-scan-sheet')).toBeNull();
  });

  test('the stamp is captured from the drawn view at the photo\'s pixel size and the ladder\'s quality', async () => {
    const host = new DeviceHostController();
    mount(<DeviceHost host={host} />);
    let out: Promise<unknown> = Promise.resolve();
    act(() => {
      out = host.requestStamp({ uri: 'file:///r.jpg', width: 1600, height: 1200, lines: ['21 Oct 2026 09:14', 'WO-1042'], quality: 0.6 });
    });
    const stamp = await screen.findByTestId('device-stamp');
    expect(screen.getByText('21 Oct 2026 09:14')).toBeTruthy();
    expect(screen.getByText('WO-1042')).toBeTruthy();
    const image = stamp.findAll((n: { props: Record<string, unknown> }) => n.props.onLoad !== undefined)[0]!;
    act(() => image.props.onLoad());
    await expect(out).resolves.toEqual({ uri: 'file:///tmp/stamped.jpg', width: 1600, height: 1200 });
    expect(captureRef).toHaveBeenCalledWith(expect.anything(), { format: 'jpg', quality: 0.6, result: 'tmpfile', width: 1600, height: 1200 });
  });
});

describe('the Esri map', () => {
  const markers = [
    { id: 'a', label: '1', lat: 41.88, lng: -87.63, tone: 'info' as const, accessibilityLabel: 'Stop 1, 22 Cedar Court' },
    { id: 'b', label: '2', lat: 41.9, lng: -87.6, tone: 'success' as const, accessibilityLabel: 'Stop 2, 4 Elm Row' },
  ];

  test('World Street Map tiles from the host given, with Esri\'s attribution; every stop a named button', () => {
    const Map = esriMapView('https://server.arcgisonline.com/');
    const onSelect = jest.fn();
    mount(<Map markers={markers} offline={false} onSelect={onSelect} selectedId="a" testID="map" />);
    expect(screen.getByTestId('url-tile').props.urlTemplate).toBe(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
    );
    expect(screen.getByTestId('map-attribution')).toHaveTextContent(ESRI_ATTRIBUTION);
    fireEvent.press(screen.getByRole('button', { name: 'Stop 2, 4 Elm Row' }));
    expect(onSelect).toHaveBeenCalledWith('b');
  });

  test('no tile host (the utility switched the basemap off): stops over a plain ground, no attribution', () => {
    const Map = esriMapView(null);
    mount(<Map markers={markers} offline={false} />);
    expect(screen.queryByTestId('url-tile')).toBeNull();
    expect(screen.queryByTestId('map-attribution')).toBeNull();
    expect(tileUrlFor('  ')).toBeNull();
  });

  test('no signal: the offline state, never a stale picture (R31)', () => {
    const Map = esriMapView('https://server.arcgisonline.com');
    mount(<Map markers={markers} offline />);
    expect(screen.getByTestId('map-offline')).toHaveTextContent('No signal. The map needs one.');
    expect(screen.queryByTestId('esri-map')).toBeNull();
  });

  test('the first view holds every stop; one stop gets a street-level view', () => {
    const r = regionFor(markers)!;
    expect(r.latitude).toBeCloseTo(41.89);
    expect(r.latitudeDelta).toBeGreaterThan(0.02);
    expect(regionFor([markers[0]!])!.latitudeDelta).toBe(0.005);
    expect(regionFor([])).toBeUndefined();
  });
});
