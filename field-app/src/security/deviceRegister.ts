/**
 * This handset's identity: a random device id minted once per install, and
 * the NAME the office knows it by.
 *
 * Security tab §4: *"Registration | Named at activation (Van 14 tablet) and
 * bound to the capture credential. The office sees every device a technician
 * uses"*. FF-57 shows it: *"Registered as Van 14 tablet. The office can see
 * which devices you use and sign one out from the back office."*
 *
 * The id is not a hardware identifier (no IMEI, no advertising id) — it is a
 * random value kept in the keystore, so it survives an app update and dies
 * with an uninstall, which is the lifetime a registration should have.
 */
import { type AuthApi, type DeviceRegistration } from './authApi';
import { type SecretStore } from './secretStore';

const DEVICE_ID_KEY = 'handset.device.id';
const DEVICE_NAME_KEY = 'handset.device.name';
const DEVICE_REGISTERED_KEY = 'handset.device.registered';

/** The server keeps 80 characters of a device label (`work/mobile.py`). */
export const DEVICE_NAME_MAX = 80;

export class DeviceNameRequiredError extends Error {
  constructor() {
    super('a device name is required');
    this.name = 'DeviceNameRequiredError';
  }
}

export function normaliseDeviceName(raw: string): string {
  const name = raw.replace(/\s+/g, ' ').trim().slice(0, DEVICE_NAME_MAX);
  if (!name) throw new DeviceNameRequiredError();
  return name;
}

export class DeviceRegister {
  constructor(
    private readonly secrets: SecretStore,
    private readonly newId: () => string,
  ) {}

  /** The device id, minted on first call and stable afterwards. */
  async deviceId(): Promise<string> {
    const existing = await this.secrets.get(DEVICE_ID_KEY);
    if (existing) return existing;
    const id = this.newId();
    await this.secrets.set(DEVICE_ID_KEY, id);
    return id;
  }

  async deviceName(): Promise<string | null> {
    return this.secrets.get(DEVICE_NAME_KEY);
  }

  async isRegistered(): Promise<boolean> {
    return (await this.secrets.get(DEVICE_REGISTERED_KEY)) === '1';
  }

  /**
   * Register by name. The name is kept locally even when the server call
   * fails (no signal at activation), so it is still offered — and sent — at
   * the next sign-in rather than asked for twice.
   */
  async register(api: AuthApi, input: { tenant: string; accessToken: string; name: string }): Promise<DeviceRegistration> {
    const name = normaliseDeviceName(input.name);
    const deviceId = await this.deviceId();
    await this.secrets.set(DEVICE_NAME_KEY, name);
    const result = await api.registerDevice({ tenant: input.tenant, accessToken: input.accessToken, deviceId, name });
    await this.secrets.set(DEVICE_REGISTERED_KEY, '1');
    return result;
  }
}
