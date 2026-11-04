/**
 * Small key state: the active technician, the technicians known on this
 * handset, the chosen language. MMKV, encrypted (Security tab §2: *"MMKV
 * preferences | Encrypted | Cheap, and it holds the active technician"*).
 *
 * The encryption key is itself a secret, so it lives in the keystore and is
 * minted once per install. A secret never goes in here — that is what
 * `SecretStore` is for.
 */
import { MMKV } from 'react-native-mmkv';

import { type SecretStore } from './secretStore';

export interface KeyValueStore {
  getString(key: string): string | undefined;
  set(key: string, value: string): void;
  delete(key: string): void;
}

export class MemoryKeyValueStore implements KeyValueStore {
  readonly data = new Map<string, string>();

  getString(key: string): string | undefined {
    return this.data.get(key);
  }

  set(key: string, value: string): void {
    this.data.set(key, value);
  }

  delete(key: string): void {
    this.data.delete(key);
  }
}

const PREFS_KEY_SECRET = 'handset.prefs.encryption-key';
/** MMKV takes an AES key of at most 16 bytes. */
const MMKV_KEY_CHARS = 16;
const KEY_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';

export function randomKey(randomBytes: (n: number) => Uint8Array, length = MMKV_KEY_CHARS): string {
  const bytes = randomBytes(length);
  let out = '';
  for (let i = 0; i < length; i += 1) {
    out += KEY_ALPHABET[(bytes[i] ?? 0) % KEY_ALPHABET.length];
  }
  return out;
}

/** Opens the app's encrypted preference store, minting its key on first run. */
export async function openEncryptedPrefs(
  secrets: SecretStore,
  randomBytes: (n: number) => Uint8Array,
): Promise<KeyValueStore> {
  let key = await secrets.get(PREFS_KEY_SECRET);
  if (!key) {
    key = randomKey(randomBytes);
    await secrets.set(PREFS_KEY_SECRET, key);
  }
  const mmkv = new MMKV({ id: 'field-prefs', encryptionKey: key });
  return {
    getString: (k) => mmkv.getString(k),
    set: (k, v) => mmkv.set(k, v),
    delete: (k) => mmkv.delete(k),
  };
}
