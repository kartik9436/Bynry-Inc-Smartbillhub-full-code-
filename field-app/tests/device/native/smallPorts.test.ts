/**
 * The small real ports, each with its native module mocked: biometric unlock,
 * the file picker, on-device dictation, *Keep screen on*, FF-07's permissions.
 */
import { Camera } from 'expo-camera';
import * as DocumentPicker from 'expo-document-picker';
import { activateKeepAwakeAsync, deactivateKeepAwake } from 'expo-keep-awake';
import * as LocalAuthentication from 'expo-local-authentication';
import * as Location from 'expo-location';
import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition';

import { PortUnavailableError, UNWIRED_DICTATION } from '../../../src/device';
import { expoBiometric } from '../../../src/device/native/biometric';
import { expoDictation } from '../../../src/device/native/dictation';
import { expoFilePicker } from '../../../src/device/native/files';
import { followKeepAwake, KEEP_AWAKE_TAG, watchedStore } from '../../../src/device/native/keepAwake';
import { expoPermissions, stateOf } from '../../../src/device/native/permissions';
import { PREF, writeFlag } from '../../../src/screens/me/prefs';
import { MemoryKeyValueStore } from '../../../src/security/prefs';

const LA = LocalAuthentication as jest.Mocked<typeof LocalAuthentication>;
const DP = DocumentPicker as jest.Mocked<typeof DocumentPicker>;
type SpeechMock = jest.Mocked<typeof ExpoSpeechRecognitionModule> & { __emit(event: string, payload: unknown): void };
const SR = ExpoSpeechRecognitionModule as SpeechMock;

beforeEach(() => jest.clearAllMocks());

describe('biometric', () => {
  test('available only with the hardware AND an enrolled finger or face', async () => {
    LA.hasHardwareAsync.mockResolvedValueOnce(true);
    LA.isEnrolledAsync.mockResolvedValueOnce(false);
    await expect(expoBiometric().isAvailable()).resolves.toBe(false);
    LA.hasHardwareAsync.mockResolvedValueOnce(true);
    LA.isEnrolledAsync.mockResolvedValueOnce(true);
    await expect(expoBiometric().isAvailable()).resolves.toBe(true);
  });

  test("passes only on the platform's success, with the prompt, and never on the device passcode", async () => {
    LA.authenticateAsync.mockResolvedValueOnce({ success: true } as never);
    await expect(expoBiometric().authenticate('Unlock as Dana')).resolves.toBe(true);
    expect(LA.authenticateAsync).toHaveBeenCalledWith({ promptMessage: 'Unlock as Dana', disableDeviceFallback: true });
    LA.authenticateAsync.mockResolvedValueOnce({ success: false, error: 'user_cancel' } as never);
    await expect(expoBiometric().authenticate('x')).resolves.toBe(false);
    LA.authenticateAsync.mockRejectedValueOnce(new Error('boom'));
    await expect(expoBiometric().authenticate('x')).resolves.toBe(false);
  });
});

describe('file picker', () => {
  test('one file, copied to the cache, mapped to the port; backing out is null', async () => {
    DP.getDocumentAsync.mockResolvedValueOnce({
      canceled: false,
      assets: [{ uri: 'file:///cache/permit.pdf', name: 'permit.pdf', size: 48213, mimeType: 'application/pdf', lastModified: 0 }],
    } as never);
    await expect(expoFilePicker().pick()).resolves.toEqual({ uri: 'file:///cache/permit.pdf', name: 'permit.pdf', bytes: 48213, mimeType: 'application/pdf' });
    expect(DP.getDocumentAsync).toHaveBeenCalledWith({ multiple: false, copyToCacheDirectory: true });
    await expect(expoFilePicker().pick()).resolves.toBeNull();
  });
});

describe('dictation', () => {
  test('a handset that cannot recognise speech ON THE DEVICE gets the refusing port, not server recognition', () => {
    SR.isRecognitionAvailable.mockReturnValueOnce(true);
    SR.supportsOnDeviceRecognition.mockReturnValueOnce(false);
    expect(expoDictation()).toBe(UNWIRED_DICTATION);
  });

  function onDevice() {
    SR.isRecognitionAvailable.mockReturnValue(true);
    SR.supportsOnDeviceRecognition.mockReturnValue(true);
    SR.requestPermissionsAsync.mockResolvedValue({ granted: true, status: 'granted' } as never);
    return expoDictation();
  }

  test('one utterance, on the device, in the app language: the final words', async () => {
    const d = onDevice();
    expect(d.available).toBe(true);
    const heard = d.listen('es-MX');
    await new Promise((r) => setTimeout(r, 0));
    expect(SR.start).toHaveBeenCalledWith(expect.objectContaining({ lang: 'es-MX', requiresOnDeviceRecognition: true, continuous: false }));
    SR.__emit('result', { isFinal: false, results: [{ transcript: 'medidor' }] });
    SR.__emit('result', { isFinal: true, results: [{ transcript: ' medidor tapado por un arbusto ' }] });
    SR.__emit('end', null);
    await expect(heard).resolves.toBe('medidor tapado por un arbusto');
  });

  test('silence is null; a real error refuses in words; a refused microphone refuses', async () => {
    const d = onDevice();
    const quiet = d.listen('en');
    await new Promise((r) => setTimeout(r, 0));
    SR.__emit('error', { error: 'no-speech', message: '' });
    await expect(quiet).resolves.toBeNull();

    const broken = d.listen('en');
    await new Promise((r) => setTimeout(r, 0));
    SR.__emit('error', { error: 'audio-capture', message: '' });
    await expect(broken).rejects.toBeInstanceOf(PortUnavailableError);

    SR.requestPermissionsAsync.mockResolvedValueOnce({ granted: false, status: 'denied' } as never);
    await expect(d.listen('en')).rejects.toBeInstanceOf(PortUnavailableError);
  });
});

describe('keep screen on', () => {
  test('follows FF-51 live: on, off, and released at the end', () => {
    const store = watchedStore(new MemoryKeyValueStore());
    const stop = followKeepAwake(store);
    expect(activateKeepAwakeAsync).not.toHaveBeenCalled();
    writeFlag(store, PREF.KEEP_AWAKE, true);
    expect(activateKeepAwakeAsync).toHaveBeenCalledWith(KEEP_AWAKE_TAG);
    writeFlag(store, PREF.THEME_MODE, true);
    expect(activateKeepAwakeAsync).toHaveBeenCalledTimes(1);
    writeFlag(store, PREF.KEEP_AWAKE, false);
    return new Promise<void>((done) =>
      setTimeout(() => {
        expect(deactivateKeepAwake).toHaveBeenCalledWith(KEEP_AWAKE_TAG);
        writeFlag(store, PREF.KEEP_AWAKE, true);
        stop();
        setTimeout(() => {
          expect(deactivateKeepAwake).toHaveBeenCalledTimes(2);
          done();
        }, 0);
      }, 0),
    );
  });
});

describe("FF-07's permissions", () => {
  test('the platform answer, as it is: granted, denied, or unknown before asking', () => {
    expect(stateOf({ granted: true, status: 'granted' })).toBe('granted');
    expect(stateOf({ granted: false, status: 'denied' })).toBe('denied');
    expect(stateOf({ granted: false, status: 'undetermined' })).toBe('unknown');
  });

  test('each kind reads its own package and can ask', async () => {
    const p = expoPermissions();
    expect(p.canRequest).toBe(true);
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValueOnce({ granted: true, status: 'granted' });
    await expect(p.status('location')).resolves.toBe('granted');
    (Camera.requestCameraPermissionsAsync as jest.Mock).mockResolvedValueOnce({ granted: false, status: 'denied' });
    await expect(p.request('camera')).resolves.toBe('denied');
    (Location.getForegroundPermissionsAsync as jest.Mock).mockRejectedValueOnce(new Error('x'));
    await expect(p.status('location')).resolves.toBe('unknown');
  });
});
