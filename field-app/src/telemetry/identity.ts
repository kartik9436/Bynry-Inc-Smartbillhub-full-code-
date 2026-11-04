/**
 * The anonymous device id — AD-19.
 *
 * A random v4 UUID minted once per install and kept in the telemetry store. It
 * is not derived from the hardware, the user, the sign-in or the tenant, so it
 * links events from one handset to each other. (The technician's own id and name
 * travel beside it since the PO's 2026-10-21 ruling — see `telemetryIdentity`.) Signing out
 * does not change it (it identifies a handset, not a person); reinstalling does.
 *
 * The id generator is injected — `expo-crypto`'s `randomUUID` on the handset.
 */
import type { KeyValueStore, TelemetryIdentity } from './types';

const DEVICE_KEY = 'telemetry.device.v1';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export function getOrCreateDeviceId(store: KeyValueStore, randomUUID: () => string): string {
  try {
    const existing = store.getString(DEVICE_KEY);
    if (existing && UUID.test(existing)) return existing;
  } catch {
    /* fall through and mint */
  }
  const id = randomUUID().toLowerCase();
  try {
    store.set(DEVICE_KEY, id);
  } catch {
    /* an id for this run only; telemetry carries on */
  }
  return id;
}

/**
 * The whole of a telemetry identity: tenant, role, the anonymous device id and —
 * since the PO ruled on 2026-10-21 that usage data may name the technician
 * ("B. Yes, by name") — the SIGNED-IN technician's id and name, from the session.
 * There is no parameter for anybody else; a customer is never an identity.
 */
export function telemetryIdentity(
  tenant: string,
  role: string,
  deviceId: string,
  technician?: { id: string; name: string },
): TelemetryIdentity {
  return technician
    ? { tenant, role, deviceId, technicianId: technician.id, technicianName: technician.name }
    : { tenant, role, deviceId };
}
