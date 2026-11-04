/**
 * The REAL biometric check behind `BiometricPort` (`../../security/biometric.ts`):
 * `expo-local-authentication`.
 *
 * It answers ONE question — did the platform confirm the phone's enrolled
 * owner — and nothing more. Who may be returned to is the session manager's
 * rule (`unlockWithBiometric` refuses anyone but the technician whose session
 * it is; switching technician always takes a password, Security §3).
 *
 * The device passcode is NOT accepted in place of the biometric
 * (`disableDeviceFallback`): a passcode on a shared van tablet is shared, and
 * the session's own password is the fallback.
 */
import * as LocalAuthentication from 'expo-local-authentication';

import type { BiometricPort } from '../../security/biometric';
import { withSystemInteraction } from '../../session/systemInteraction';

export function expoBiometric(): BiometricPort {
  return {
    async isAvailable() {
      try {
        const [hardware, enrolled] = await Promise.all([LocalAuthentication.hasHardwareAsync(), LocalAuthentication.isEnrolledAsync()]);
        return hardware && enrolled;
      } catch {
        return false;
      }
    },
    async authenticate(prompt: string) {
      try {
        // The fingerprint prompt is the app's own pop-up; never "leaving" (MQ-019).
        const result = await withSystemInteraction(() =>
          LocalAuthentication.authenticateAsync({ promptMessage: prompt, disableDeviceFallback: true }),
        );
        return result.success === true;
      } catch {
        return false;
      }
    },
  };
}
