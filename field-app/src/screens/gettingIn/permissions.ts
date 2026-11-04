/**
 * FF-07's three permissions, as a port: Location (*stamps readings and
 * photos*), Camera (*photos and barcode scanning*), Notifications
 * (*emergency jobs reach you*).
 *
 * ⚠ The native build passes the real port (`device/native/permissions.ts`,
 * 2026-10-21). This default is for tests and previews: as first written,
 * NONE OF THE THREE PLATFORM PACKAGES WAS INSTALLED (`expo-location`,
 * `expo-camera`, `expo-notifications`), and adding them is the
 * coordinator's call. So the shipped port answers `unknown` for every one
 * and cannot ask — FF-07 then offers *Open settings*, which React Native can
 * do on its own (`Linking.openSettings`). It never shows ALLOWED for a
 * permission it could not read.
 */
import { Linking } from 'react-native';

import { withSystemInteraction } from '../../session/systemInteraction';

export const PERMISSIONS = ['location', 'camera', 'notifications'] as const;
export type PermissionKind = (typeof PERMISSIONS)[number];
export type PermissionState = 'granted' | 'denied' | 'unknown';

export interface PermissionsPort {
  status(kind: PermissionKind): Promise<PermissionState>;
  /** Ask the platform. Resolves to the state after asking. */
  request(kind: PermissionKind): Promise<PermissionState>;
  /** Can this port ask at all (a package is installed)? */
  canRequest: boolean;
  /** Refused, and the platform will not ask again: only the settings can change it (DEF-FLD-10605). */
  blocked?(kind: PermissionKind): Promise<boolean>;
  openSettings(): Promise<void>;
}

export const permissionsNotWired: PermissionsPort = {
  status: async () => 'unknown',
  request: async () => 'unknown',
  canRequest: false,
  // The app's own settings visit never counts as leaving (MQ-019, DEF-FLD-10614).
  openSettings: () => withSystemInteraction(() => Linking.openSettings(), { untilReturn: true }),
};
