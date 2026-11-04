/* Native modules Jest cannot load: reanimated and safe-area-context use their own mocks. */
jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

/*
 * The device packages the dependency lane installed (CR-187-BRC10). Each is a
 * set of jest.fn()s with a neutral default — "nothing granted, nothing there"
 * — so a test that does not care sees an honest empty handset, and a test that
 * does sets the answer it needs (`tests/device/native/*`). No test reaches a
 * real native module.
 */
const mockDenied = { granted: false, status: 'undetermined', canAskAgain: true, expires: 'never' };

jest.mock('expo-camera', () => {
  const React = require('react');
  const { View } = require('react-native');
  const CameraView = React.forwardRef(function CameraView(props, ref) {
    React.useImperativeHandle(ref, () => ({ takePictureAsync: (...a) => mockCamera.takePictureAsync(...a) }));
    return React.createElement(View, { testID: props.testID ?? 'camera-view' });
  });
  const mockCamera = {
    takePictureAsync: jest.fn(async () => ({ uri: 'file:///camera/shot.jpg', width: 4032, height: 3024 })),
    permission: { granted: true, status: 'granted', canAskAgain: true, expires: 'never' },
  };
  return {
    __mock: mockCamera,
    CameraView,
    useCameraPermissions: () => [mockCamera.permission, jest.fn(async () => mockCamera.permission)],
    Camera: {
      getCameraPermissionsAsync: jest.fn(async () => mockDenied),
      requestCameraPermissionsAsync: jest.fn(async () => mockDenied),
    },
  };
});

/* OQ-FLD-12797 — the pinning module is native; a test binary has none, exactly like Expo Go. */
jest.mock('react-native-ssl-public-key-pinning', () => ({
  isSslPinningAvailable: jest.fn(() => false),
  initializeSslPinning: jest.fn(async () => undefined),
  disableSslPinning: jest.fn(async () => undefined),
  addSslPinningErrorListener: jest.fn(() => ({ remove: jest.fn() })),
}));

jest.mock('expo-image-manipulator', () => ({
  SaveFormat: { JPEG: 'jpeg', PNG: 'png', WEBP: 'webp' },
  manipulateAsync: jest.fn(async (uri) => ({ uri: `${uri}#m`, width: 4032, height: 3024 })),
}));

jest.mock('react-native-view-shot', () => ({
  captureRef: jest.fn(async () => 'file:///tmp/stamped.jpg'),
}));

jest.mock('expo-location', () => ({
  Accuracy: { Lowest: 1, Low: 2, Balanced: 3, High: 4, Highest: 5, BestForNavigation: 6 },
  getForegroundPermissionsAsync: jest.fn(async () => mockDenied),
  requestForegroundPermissionsAsync: jest.fn(async () => mockDenied),
  getCurrentPositionAsync: jest.fn(async () => null),
  getLastKnownPositionAsync: jest.fn(async () => null),
  watchPositionAsync: jest.fn(async () => ({ remove: jest.fn() })),
  hasServicesEnabledAsync: jest.fn(async () => true),
  enableNetworkProviderAsync: jest.fn(async () => undefined),
}));

jest.mock('expo-notifications', () => ({
  AndroidImportance: { UNKNOWN: 0, UNSPECIFIED: 1, NONE: 2, MIN: 3, LOW: 4, DEFAULT: 5, HIGH: 6, MAX: 7 },
  AndroidNotificationVisibility: { UNKNOWN: 0, PUBLIC: 1, PRIVATE: 2, SECRET: 3 },
  setNotificationChannelAsync: jest.fn(async (id, ch) => ({ id, ...ch })),
  setNotificationHandler: jest.fn(),
  addNotificationReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  addNotificationResponseReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  getPermissionsAsync: jest.fn(async () => mockDenied),
  requestPermissionsAsync: jest.fn(async () => mockDenied),
  getDevicePushTokenAsync: jest.fn(async () => ({ type: 'android', data: '' })),
  scheduleNotificationAsync: jest.fn(async () => 'local-1'),
}));

jest.mock('expo-local-authentication', () => ({
  hasHardwareAsync: jest.fn(async () => false),
  isEnrolledAsync: jest.fn(async () => false),
  authenticateAsync: jest.fn(async () => ({ success: false, error: 'not_available' })),
}));

jest.mock('expo-document-picker', () => ({
  getDocumentAsync: jest.fn(async () => ({ canceled: true, assets: null })),
}));

/* FB-031 — the document opener's two packages: Android's intent, iOS's sheet. */
jest.mock('expo-intent-launcher', () => ({
  startActivityAsync: jest.fn(async () => ({ resultCode: 0 })),
}));

jest.mock('expo-sharing', () => ({
  isAvailableAsync: jest.fn(async () => true),
  shareAsync: jest.fn(async () => undefined),
}));

jest.mock('expo-keep-awake', () => ({
  activateKeepAwakeAsync: jest.fn(async () => undefined),
  deactivateKeepAwake: jest.fn(async () => undefined),
}));

jest.mock('expo-speech-recognition', () => {
  const listeners = {};
  const ExpoSpeechRecognitionModule = {
    isRecognitionAvailable: jest.fn(() => false),
    supportsOnDeviceRecognition: jest.fn(() => false),
    requestPermissionsAsync: jest.fn(async () => mockDenied),
    start: jest.fn(),
    stop: jest.fn(),
    abort: jest.fn(),
    addListener: jest.fn((event, fn) => {
      (listeners[event] = listeners[event] || []).push(fn);
      return { remove: () => (listeners[event] = (listeners[event] || []).filter((f) => f !== fn)) };
    }),
    /* Test helper: emit an event to every listener. */
    __emit: (event, payload) => (listeners[event] || []).slice().forEach((f) => f(payload)),
  };
  return { ExpoSpeechRecognitionModule };
});

jest.mock('react-native-maps', () => {
  const React = require('react');
  const { View } = require('react-native');
  const MapView = (props) => React.createElement(View, { testID: props.testID ?? 'map-view' }, props.children);
  const Marker = (props) => React.createElement(View, { testID: props.testID, accessibilityLabel: props.accessibilityLabel }, props.children);
  const UrlTile = (props) => React.createElement(View, { testID: 'url-tile', urlTemplate: props.urlTemplate });
  return { __esModule: true, default: MapView, Marker, UrlTile };
});

jest.mock('@react-native-firebase/crashlytics', () => {
  const instance = {};
  return {
    getCrashlytics: jest.fn(() => instance),
    log: jest.fn(),
    setAttributes: jest.fn(async () => null),
    setUserId: jest.fn(async () => null),
    recordError: jest.fn(),
  };
});

jest.mock('@react-native-firebase/app', () => ({ getApp: jest.fn(() => ({})), getApps: jest.fn(() => [{}]) }));

/*
 * DEF-FLD-10627 — the signing pad draws in a WebView, which Jest cannot host.
 * The mock is a View whose ref answers like the real pad: `readSignature()`
 * calls `onOK` with `__mock.dataUrl`, or `onEmpty` when that is null;
 * `__mock.last` holds the props, so a test can call `onBegin` (a finger
 * touching the pad).
 */
jest.mock('react-native-signature-canvas', () => {
  const React = require('react');
  const { View } = require('react-native');
  const mockPad = { dataUrl: null, clearSignature: jest.fn(), last: null };
  const SignatureView = React.forwardRef(function SignatureView(props, ref) {
    mockPad.last = props;
    React.useImperativeHandle(ref, () => ({
      readSignature: () => (mockPad.dataUrl ? props.onOK?.(mockPad.dataUrl) : props.onEmpty?.()),
      clearSignature: () => mockPad.clearSignature(),
    }));
    return React.createElement(View, { testID: 'signature-canvas' });
  });
  return { __esModule: true, __mock: mockPad, default: SignatureView };
});
