/**
 * Biometric unlock, as a port.
 *
 * Security tab §3: *"Offered for returning to your own session. Switching
 * technician always takes a password — a thumb on a shared tablet is not an
 * identity claim."* The session manager enforces the second half; this port
 * only answers "did the person holding the phone pass the platform's check".
 *
 * ⚠ WIRED in the native build (`device/native/biometric.ts`, 2026-10-21); this
 * default is for tests. As first written: the package (`expo-local-authentication`) was NOT installed
 * in `field-app/` and adding dependencies is the coordinator's call, so the
 * shipped port reports biometrics as unavailable and FF-05's *Use fingerprint*
 * stays off until it is added. Nothing pretends to have checked a thumb.
 */
export interface BiometricPort {
  isAvailable(): Promise<boolean>;
  /** Resolves true only when the platform confirmed the enrolled owner. */
  authenticate(prompt: string): Promise<boolean>;
}

export const unavailableBiometric: BiometricPort = {
  isAvailable: async () => false,
  authenticate: async () => false,
};
