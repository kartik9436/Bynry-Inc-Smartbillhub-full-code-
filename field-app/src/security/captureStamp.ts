/**
 * The stamp every captured item carries.
 *
 * Security tab §3, *"Signed by whom"*: `captured_by` is written at capture
 * FROM THE CAPTURE CREDENTIAL, never read from the current session. *"That
 * one line is what makes a shared handset honest."* So this function takes a
 * credential and nothing else — there is no session in its signature to read
 * by mistake.
 *
 * The server checks `capture_token` per item today (BR-WRK-059: the session
 * that SENDS is only the courier). The design's device-held signature on top
 * of it is not on the server yet (`device-signature` in `SERVER_GAPS`), so
 * the stamp carries the device id for it to be checked against once it is.
 */
import { type CaptureCredential, isCaptureValid } from './credentials';

export interface CaptureStamp {
  /** The technician who captured the item — the credential's, always. */
  captured_by: string;
  /** The server's signed token for that technician (BR-WRK-059). */
  capture_token: string;
  /** The registered handset. */
  device_id: string;
  /** The phone's clock at capture (R92: both clocks are kept). */
  captured_at: string;
}

export class CaptureCredentialExpiredError extends Error {
  readonly technicianId: string;

  constructor(technicianId: string) {
    super('capture credential expired — a password is needed before anything more is captured');
    this.name = 'CaptureCredentialExpiredError';
    this.technicianId = technicianId;
  }
}

export function stampFromCredential(cred: CaptureCredential, now: number): CaptureStamp {
  if (!isCaptureValid(cred, now)) throw new CaptureCredentialExpiredError(cred.technicianId);
  return {
    captured_by: cred.technicianId,
    capture_token: cred.serverToken,
    device_id: cred.deviceId,
    captured_at: new Date(now).toISOString(),
  };
}
