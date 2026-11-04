/**
 * FF-07's three permissions, for real (`PermissionsPort`,
 * `screens/gettingIn/permissions.ts`): location from `expo-location`, the
 * camera from `expo-camera`, notifications from `expo-notifications` — asked
 * with iOS Critical Alerts, so an emergency breaks through silent mode
 * (ADR-012). The platform's answer is reported as it is: granted, denied, or
 * unknown while it has not been asked.
 */
import { Camera } from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import { Linking } from 'react-native';

import type { PermissionKind, PermissionsPort, PermissionState } from '../../screens/gettingIn/permissions';
import { withSystemInteraction } from '../../session/systemInteraction';
import { IOS_PERMISSION_REQUEST } from './notifications';

interface Answer {
  granted: boolean;
  status: string;
  canAskAgain?: boolean;
}

export function stateOf(answer: Answer): PermissionState {
  if (answer.granted || answer.status === 'granted') return 'granted';
  if (answer.status === 'denied') return 'denied';
  return 'unknown';
}

export function expoPermissions(onGranted?: (kind: PermissionKind) => void): PermissionsPort {
  const read = async (kind: PermissionKind): Promise<Answer> => {
    switch (kind) {
      case 'location':
        return Location.getForegroundPermissionsAsync();
      case 'camera':
        return Camera.getCameraPermissionsAsync();
      default:
        return Notifications.getPermissionsAsync();
    }
  };
  // The platform's dialog is the app's own pop-up: Android reports it as
  // backgrounding, and it must never count as leaving (MQ-019, DEF-FLD-10614).
  const ask = (kind: PermissionKind): Promise<Answer> =>
    withSystemInteraction(async (): Promise<Answer> => {
      switch (kind) {
        case 'location':
          return Location.requestForegroundPermissionsAsync();
        case 'camera':
          return Camera.requestCameraPermissionsAsync();
        default:
          return Notifications.requestPermissionsAsync(IOS_PERMISSION_REQUEST);
      }
    });
  return {
    canRequest: true,
    async status(kind) {
      try {
        return stateOf(await read(kind));
      } catch {
        return 'unknown';
      }
    },
    async request(kind) {
      try {
        const state = stateOf(await ask(kind));
        if (state === 'granted') onGranted?.(kind);
        return state;
      } catch {
        return 'unknown';
      }
    },
    // DEF-FLD-10605: refused and the platform will not show its question
    // again — only the app's settings can turn it on (Nearby's *Turn on location*).
    async blocked(kind) {
      try {
        const answer = await read(kind);
        return stateOf(answer) !== 'granted' && answer.canAskAgain === false;
      } catch {
        return false;
      }
    },
    // Held until the app is active again — openSettings resolves on launch (MQ-019).
    openSettings: () => withSystemInteraction(() => Linking.openSettings(), { untilReturn: true }),
  };
}
