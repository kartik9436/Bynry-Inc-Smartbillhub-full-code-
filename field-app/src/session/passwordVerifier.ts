/**
 * Checking a password with no signal.
 *
 * Auto-lock fires five minutes after the last touch and after five minutes
 * away from the app (Security tab §3 as amended 2026-10-26, MQ-019 — it read
 * *"on every trip to the background"* until then), and a technician spends whole shifts with no
 * signal. So unlocking — and handing the phone back to a technician who has
 * already signed in on it today — must work offline, against a verifier kept
 * in the keystore at the last online sign-in. Never the password itself.
 *
 * ⚠ **THE HASH IS A PLAIN SALTED SHA-256, NOT A SLOW KEY-DERIVATION
 * FUNCTION.** `expo-crypto` offers digests and random bytes and no PBKDF2 or
 * scrypt; adding a native crypto package is a dependency decision for the
 * coordinator. The verifier sits in the hardware keystore, which is the
 * control doing the work, but a slow KDF is the right construction and is
 * reported as such rather than claimed.
 */
import { type SecretStore, secretKey } from '../security/secretStore';

export type HashFn = (input: string) => Promise<string>;

interface StoredVerifier {
  salt: string;
  hash: string;
}

export class PasswordVerifier {
  constructor(
    private readonly secrets: SecretStore,
    private readonly sha256: HashFn,
    private readonly newSalt: () => string,
  ) {}

  private key(technicianId: string): string {
    return secretKey('handset', 'verifier', technicianId);
  }

  /** Called after the SERVER accepted the password. */
  async remember(technicianId: string, password: string): Promise<void> {
    const salt = this.newSalt();
    const hash = await this.sha256(`${salt}:${password}`);
    const value: StoredVerifier = { salt, hash };
    await this.secrets.set(this.key(technicianId), JSON.stringify(value));
  }

  /** `null` when this handset has never seen this technician sign in. */
  async check(technicianId: string, password: string): Promise<boolean | null> {
    const raw = await this.secrets.get(this.key(technicianId));
    if (!raw) return null;
    let stored: StoredVerifier;
    try {
      stored = JSON.parse(raw) as StoredVerifier;
    } catch {
      return null;
    }
    const hash = await this.sha256(`${stored.salt}:${password}`);
    return hash === stored.hash;
  }

  async forget(technicianId: string): Promise<void> {
    await this.secrets.remove(this.key(technicianId));
  }
}
