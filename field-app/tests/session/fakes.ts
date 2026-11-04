/**
 * In-memory stand-ins for the server, the outbox and the platform, so the
 * whole multi-technician session can be walked through a shift in Node.
 */
import {
  type ActivationLookup,
  type AuthApi,
  type CaptureTokenResult,
  DeviceSignedOutError,
  InvalidCredentialsError,
  OfflineError,
  type SignInResult,
} from '../../src/security/authApi';
import { type BiometricPort } from '../../src/security/biometric';
import { HOUR_MS, ManualClock } from '../../src/security/clock';
import { DeviceRegister } from '../../src/security/deviceRegister';
import { MemoryKeyValueStore } from '../../src/security/prefs';
import { MemorySecretStore } from '../../src/security/secretStore';
import { type OutboxPort, type UnsentCount } from '../../src/session/outboxPort';
import { PasswordVerifier } from '../../src/session/passwordVerifier';
import { SessionManager } from '../../src/session/sessionManager';

export const TENANT = 'silver-creek';

/** 07:30 on 21 October 2026, local to nobody — the clock only has to move. */
export const SHIFT_START = Date.UTC(2026, 9, 21, 7, 30);

interface Person {
  password: string;
  technicianId: string;
  userId: string;
  name: string;
}

export const PEOPLE: Record<string, Person> = {
  'd.ortiz': { password: 'valley-day-0730', technicianId: 'tech-dana', userId: 'user-dana', name: 'D. Ortiz' },
  'm.chen': { password: 'evening-1600', technicianId: 'tech-marco', userId: 'user-marco', name: 'M. Chen' },
  'r.patel': { password: 'apex-contract', technicianId: 'tech-patel', userId: 'user-patel', name: 'R. Patel' },
};

/** The server: online or not, and a counter so every token is distinguishable. */
export class FakeAuthApi implements AuthApi {
  online = true;
  signedOutDevices = new Set<string>();
  issued = 0;
  calls: string[] = [];

  private offline(): void {
    if (!this.online) throw new OfflineError();
  }

  async signIn(input: { tenant: string; login: string; password: string; deviceId: string }): Promise<SignInResult> {
    this.calls.push(`signIn:${input.login}`);
    this.offline();
    const p = PEOPLE[input.login];
    if (!p || p.password !== input.password) throw new InvalidCredentialsError();
    this.issued += 1;
    return {
      access: { token: `access-${p.technicianId}-${this.issued}`, expiresInSeconds: 3600 },
      user: { id: p.userId, displayName: p.name, role: 'FIELD_TECHNICIAN' },
      technician: { id: p.technicianId, displayName: p.name },
    };
  }

  async refreshAccess(input: { tenant: string; accessToken: string; deviceId: string }) {
    this.calls.push('refresh');
    this.offline();
    if (this.signedOutDevices.has(input.deviceId)) throw new DeviceSignedOutError();
    this.issued += 1;
    return { token: `${input.accessToken}-r${this.issued}`, expiresInSeconds: 3600 };
  }

  async signOut() {
    this.calls.push('signOut');
    this.offline();
  }

  async issueCaptureToken(input: { tenant: string; accessToken: string; deviceName: string }): Promise<CaptureTokenResult> {
    this.calls.push('captureToken');
    this.offline();
    this.issued += 1;
    const tech = input.accessToken.split('-').slice(1, 3).join('-');
    // The server's own answer today: seven days.
    return { captureToken: `capture-${tech}-${this.issued}`, maxAgeSeconds: 7 * 24 * 3600, technicianName: tech };
  }

  async registerDevice(input: { deviceId: string; name: string }) {
    this.offline();
    return { deviceId: input.deviceId, name: input.name };
  }

  /** No code is known to this fake server unless a test teaches it one (`gateSupport.teachActivation`). */
  async lookupActivationCode(_input: { code: string; deviceId: string }): Promise<ActivationLookup> {
    throw new InvalidCredentialsError();
  }

  async checkActivationCode(): Promise<never> {
    throw new Error('not used here');
  }

  async completeActivation(): Promise<never> {
    throw new Error('not used here');
  }
}

/** One row per captured thing. `sent` rows are gone from "unsent". */
export interface OutboxRow {
  key: string;
  technicianId: string;
  kind: 'item' | 'photo';
  sent: boolean;
}

export class MemoryOutbox implements OutboxPort {
  rows: OutboxRow[] = [];
  mirror = new Map<string, string[]>();
  mirrorDrops: string[] = [];

  add(technicianId: string, kind: 'item' | 'photo', key: string): void {
    this.rows.push({ key, technicianId, kind, sent: false });
  }

  /** The thing the session layer must never do. Exists so the red proof can call it. */
  purgeTechnician(technicianId: string): void {
    this.rows = this.rows.filter((r) => r.technicianId !== technicianId);
  }

  unsentKeys(): string[] {
    return this.rows.filter((r) => !r.sent).map((r) => `${r.technicianId}:${r.key}`).sort();
  }

  async unsentCounts(): Promise<UnsentCount[]> {
    const by = new Map<string, UnsentCount>();
    for (const r of this.rows) {
      if (r.sent) continue;
      const c = by.get(r.technicianId) ?? { technicianId: r.technicianId, items: 0, photos: 0 };
      if (r.kind === 'photo') c.photos += 1;
      else c.items += 1;
      by.set(r.technicianId, c);
    }
    return [...by.values()];
  }

  async dropMirror(technicianId: string): Promise<void> {
    this.mirrorDrops.push(technicianId);
    this.mirror.delete(technicianId);
  }
}

export class FakeBiometric implements BiometricPort {
  available = true;
  passes = true;

  async isAvailable() {
    return this.available;
  }

  async authenticate() {
    return this.passes;
  }
}

/** A deterministic, NOT cryptographic, digest: enough to tell two passwords apart in a test. */
async function testDigest(input: string): Promise<string> {
  let h = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16);
}

export function makeHandset() {
  const clock = new ManualClock(SHIFT_START);
  const api = new FakeAuthApi();
  const secrets = new MemorySecretStore();
  const prefs = new MemoryKeyValueStore();
  const outbox = new MemoryOutbox();
  const biometric = new FakeBiometric();
  let n = 0;
  const device = new DeviceRegister(secrets, () => `device-${(n += 1)}`);
  let salt = 0;
  const verifier = new PasswordVerifier(secrets, testDigest, () => `salt-${(salt += 1)}`);
  const build = () => new SessionManager({ api, secrets, prefs, clock, device, verifier, outbox, biometric });
  const session = build();
  return { clock, api, secrets, prefs, outbox, biometric, device, verifier, session, build, HOUR_MS };
}

export async function signIn(session: SessionManager, login: string) {
  const p = PEOPLE[login];
  if (!p) throw new Error(login);
  return session.signIn({ tenant: TENANT, login, password: p.password });
}
