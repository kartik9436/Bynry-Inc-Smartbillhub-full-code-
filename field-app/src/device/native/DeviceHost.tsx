/**
 * THE DEVICE HOST — mounted once at the app root (inside the theme and the
 * words), it draws what the real camera, scanner and stamp need on screen
 * (`host.ts` says why they need a host at all):
 *
 *   - the full-screen VIEWFINDER for a photograph: the live camera, *Take the
 *     photo* and *Cancel*. Camera only — there is no gallery button (R93).
 *     It opens ONLY when no screen shows the camera inline: RW-14 draws
 *     `InlineCameraPreview` (DEF-FLD-10630, FB-002) and its shutter shoots
 *     from that view;
 *   - the full-screen SCANNER, only when a scan is on and no screen draws its
 *     own preview; *Close* ends the session without a code;
 *   - the STAMP COMPOSITOR: the resized photograph with its stamp lines laid
 *     into a view of the photograph's own pixel size, captured as a JPEG at the
 *     ladder's quality step by `react-native-view-shot` — so the stamp is IN the
 *     pixels (R94). It sits behind an invisible wrapper: the wrapper's opacity
 *     is applied by its parent when the screen is drawn, and the capture draws
 *     the child itself, so nothing flashes and the capture is opaque.
 *
 * ⚠ The capture of an off-screen view is proved here only against a mocked
 * `captureRef`; it must be walked on a real Android and iOS handset (T-62's
 * device pass) before the photograph contract is called proved on hardware.
 */
import { CameraView, useCameraPermissions } from 'expo-camera';
import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { Image, Modal, PixelRatio, Text, View } from 'react-native';
import { useTranslation } from 'react-i18next';
import { captureRef } from 'react-native-view-shot';

import { Button, Notice } from '../../components';
import { useTheme, withAlpha } from '../../theme';
import { color } from '../../tokens';
import { withSystemInteraction } from '../../session/systemInteraction';
import { CameraUnavailableError } from '../photo';
import { CAPTURE_QUALITY } from './camera';
import type { DeviceHostController, StampJob } from './host';
import { barcodeTypesFor, codeOf } from './scanner';

function useHost(host: DeviceHostController): number {
  return useSyncExternalStore(
    (cb) => host.subscribe(cb),
    () => host.version,
    () => host.version,
  );
}

/** Ask for the camera once when it is needed and not yet answered. */
function useCameraAllowed(): boolean | null {
  const [permission, request] = useCameraPermissions();
  useEffect(() => {
    // The camera question is the app's own pop-up; never "leaving" (MQ-019).
    if (permission && !permission.granted && permission.canAskAgain) void withSystemInteraction(() => request());
  }, [permission, request]);
  if (!permission) return null;
  return permission.granted;
}

export function DeviceHost({ host }: { host: DeviceHostController }) {
  useHost(host);
  useEffect(() => host.hostMounted(), [host]);
  const stamp = host.stamps[0];
  return (
    <>
      {host.camera ? <Viewfinder host={host} /> : null}
      {host.fullScreenScan ? <ScannerSheet host={host} /> : null}
      {stamp ? <StampCompositor key={stamp.id} job={stamp} /> : null}
    </>
  );
}

function Viewfinder({ host }: { host: DeviceHostController }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const allowed = useCameraAllowed();
  const camera = useRef<CameraView>(null);
  const request = host.camera;
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Refused at the platform: the screen says the camera is not available.
    if (allowed === false) request?.reject(new CameraUnavailableError());
  }, [allowed, request]);

  const shoot = async () => {
    if (!request || !camera.current) return;
    setBusy(true);
    try {
      const pic = await camera.current.takePictureAsync({ quality: CAPTURE_QUALITY, exif: false });
      request.resolve(pic ? { uri: pic.uri, width: pic.width, height: pic.height } : null);
    } catch (err) {
      request.reject(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal visible animationType="slide" onRequestClose={() => request?.resolve(null)} testID="device-viewfinder">
      <View style={{ flex: 1, backgroundColor: theme.colors.toastFill }}>
        {allowed ? <CameraView ref={camera} style={{ flex: 1 }} facing="back" testID="device-camera" /> : <View style={{ flex: 1 }} />}
        <View style={{ flexDirection: 'row', gap: theme.space[3], padding: theme.space[4] }}>
          <Button grow onPress={() => request?.resolve(null)} testID="device-camera-cancel">
            {t('field.common.cancel')}
          </Button>
          <Button grow variant="primary" busy={busy} disabled={!allowed} onPress={() => void shoot()} testID="device-camera-shutter">
            {t('field.reads.rw14.take')}
          </Button>
        </View>
      </View>
    </Modal>
  );
}

/**
 * `CameraPort.Preview` — the camera's live view drawn INSIDE a screen (RW-14,
 * DEF-FLD-10630). It registers its shutter with the host, so the screen's own
 * *Take the photo* takes the picture from this view and the full-screen
 * viewfinder does not open. Refused at the platform, it draws nothing and
 * registers nothing — the full-screen path then refuses in words as before.
 */
export function InlineCameraPreview({ host }: { host: DeviceHostController }) {
  const allowed = useCameraAllowed();
  const camera = useRef<CameraView>(null);
  useEffect(() => {
    if (!allowed) return undefined;
    return host.cameraPreviewMounted(async () => {
      if (!camera.current) return null;
      const pic = await camera.current.takePictureAsync({ quality: CAPTURE_QUALITY, exif: false });
      return pic ? { uri: pic.uri, width: pic.width, height: pic.height } : null;
    });
  }, [host, allowed]);
  if (!allowed) return null;
  return <CameraView ref={camera} style={{ flex: 1 }} facing="back" testID="device-camera-inline" />;
}

/** The live view with the session's formats — inline (FF-38) or full screen. */
function ScanCamera({ host, fill }: { host: DeviceHostController; fill: boolean }) {
  const { t } = useTranslation();
  const allowed = useCameraAllowed();
  const formats = host.scan?.formats ?? [];
  if (allowed === false) {
    return (
      <Notice tone="warning" testID="device-scan-refused">
        {t('field.ff38.cannotScan')}
      </Notice>
    );
  }
  if (!allowed) return null;
  return (
    <CameraView
      testID="device-scanner"
      style={fill ? { flex: 1 } : { width: '100%', aspectRatio: 1 }}
      facing="back"
      enableTorch={host.torch}
      barcodeScannerSettings={{ barcodeTypes: barcodeTypesFor(formats) }}
      onBarcodeScanned={(result) => {
        const code = codeOf(result);
        if (code) host.codeRead(code);
      }}
    />
  );
}

/** `ScannerPort.Preview` — a screen's own viewfinder; the host then draws none. */
export function InlineScanPreview({ host }: { host: DeviceHostController }) {
  useHost(host);
  useEffect(() => host.previewMounted(), [host]);
  return <ScanCamera host={host} fill={false} />;
}

function ScannerSheet({ host }: { host: DeviceHostController }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <Modal visible animationType="slide" onRequestClose={() => host.closeScan()} testID="device-scan-sheet">
      <View style={{ flex: 1, backgroundColor: theme.colors.toastFill }}>
        <ScanCamera host={host} fill />
        <View style={{ flexDirection: 'row', gap: theme.space[3], padding: theme.space[4] }}>
          <Button grow onPress={() => host.closeScan()} testID="device-scan-close">
            {t('field.common.close')}
          </Button>
          <Button grow onPress={() => host.setTorch(!host.torch)} testID="device-scan-torch">
            {host.torch ? t('field.ff38.torchOff') : t('field.ff38.torchOn')}
          </Button>
        </View>
      </View>
    </Modal>
  );
}

/**
 * The stamp is EVIDENCE, burned into the photograph: it looks the same
 * whichever theme the handset is in, so it reads from the palette and not
 * from the theme — white on a black band at 55%.
 */
const STAMP_INK = color.white;
const STAMP_BAND = withAlpha(color.black, 0.55);
const STAMP_BAND_UNDER = color.black;

/** The stamp's text size: a fixed share of the photograph's short side, in pixels. */
export function stampTextPx(width: number, height: number): number {
  return Math.max(14, Math.round(Math.min(width, height) * 0.03));
}

function StampCompositor({ job }: { job: StampJob }) {
  const theme = useTheme();
  const shot = useRef<View>(null);
  const ratio = PixelRatio.get() || 1;
  const w = job.width / ratio;
  const h = job.height / ratio;
  const fontSize = stampTextPx(job.width, job.height) / ratio;
  const pad = fontSize * 0.6;

  const capture = () => {
    // One frame after the image has drawn.
    requestAnimationFrame(() => {
      captureRef(shot, { format: 'jpg', quality: job.quality, result: 'tmpfile', width: job.width, height: job.height }).then(
        (uri) => job.resolve({ uri, width: job.width, height: job.height }),
        (err: unknown) => job.reject(err),
      );
    });
  };

  return (
    <View pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, width: w, height: h, opacity: 0 }} testID="device-stamp">
      <View ref={shot} collapsable={false} style={{ width: w, height: h, backgroundColor: STAMP_BAND_UNDER }}>
        <Image
          source={{ uri: job.uri }}
          style={{ width: w, height: h }}
          resizeMode="cover"
          onLoad={capture}
          onError={() => job.reject(new Error('the photograph could not be drawn for its stamp'))}
        />
        <View style={{ position: 'absolute', left: 0, right: 0, bottom: 0, padding: pad, backgroundColor: STAMP_BAND }}>
          {job.lines.map((line, i) => (
            <Text key={i} style={{ color: STAMP_INK, fontSize, lineHeight: fontSize * 1.25, fontFamily: theme.fonts.semibold }}>
              {line}
            </Text>
          ))}
        </View>
      </View>
    </View>
  );
}
