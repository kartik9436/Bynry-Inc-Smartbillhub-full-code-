/**
 * Where secrets live: the platform keystore (Secure Enclave / Android
 * Keystore) through `expo-secure-store`, and NOWHERE else.
 *
 * Security tab §2: *"The capture credential | Keystore / Secure Enclave |
 * Hardware-backed, non-exportable. It never touches the database."* So the
 * capture credential, the access token and the device secret are written here
 * and never into SQLite or MMKV. This interface exists so a test can run the
 * whole session model in Node with an in-memory store; the app wires the
 * keystore one.
 */
import * as SecureStore from 'expo-secure-store';

export interface SecretStore {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

/**
 * Keys the keystore allows are `[A-Za-z0-9._-]`, so a technician id is folded
 * into that alphabet rather than trusted to already be in it.
 */
export function secretKey(...parts: string[]): string {
  return parts.map((p) => p.replace(/[^A-Za-z0-9._-]/g, '_')).join('.');
}

export const keystoreSecretStore: SecretStore = {
  get: (key) => SecureStore.getItemAsync(key),
  set: (key, value) =>
    SecureStore.setItemAsync(key, value, {
      // Readable only once the handset has been unlocked since boot, and never
      // copied to another device by a backup restore: the capture credential
      // is DEVICE-bound, and a restored copy on a new phone would sign items
      // as a device the office never registered.
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    }),
  remove: (key) => SecureStore.deleteItemAsync(key),
};

/** For tests and for previews. Never used by the shipped app. */
export class MemorySecretStore implements SecretStore {
  readonly data = new Map<string, string>();

  async get(key: string): Promise<string | null> {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }

  async set(key: string, value: string): Promise<void> {
    this.data.set(key, value);
  }

  async remove(key: string): Promise<void> {
    this.data.delete(key);
  }
}
