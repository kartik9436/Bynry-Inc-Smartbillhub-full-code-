/**
 * Several technicians, one handset (T-12; Security tab §1 and §3; rules R25,
 * R60, R64, R113–R115; requirement 3).
 *
 * WHAT THIS GUARANTEES, each with the test that holds it
 * (`tests/session/`):
 *
 *  1. **Each technician has their own session and their own capture
 *     credential**, kept in the keystore under their own id. Marco signing in
 *     does not touch Dana's credential.
 *  2. **`captured_by` comes from the capture credential, never the current
 *     session.** `stampCapture()` reads the ACTIVE technician's credential and
 *     hands it to `stampFromCredential`, which has no session in its
 *     signature. An item captured by Dana and SENT while Marco is signed in
 *     still says Dana — the sending session is only the courier (BR-WRK-059).
 *  3. **Expiry blocks SENDING, never capture.** The access token (one hour)
 *     gates `courierAccessToken()`; the capture credential (seven days) gates
 *     `stampCapture()`. Nine hours in a valley with an expired access token is
 *     a full day of capture and a queue that goes up at the next signal.
 *  4. **Nothing unsent is ever discarded to solve an auth problem.** Sign-out,
 *     expiry, lock, switching technician and a remote sign-out all leave the
 *     outbox alone — the only port into it (`OutboxPort`) has no delete.
 *  5. **A technician never sees another's unsent work as their own.**
 *     `unsentSummary()` splits MINE from OTHERS by the owner on each count;
 *     the others are shown under their own names (FF-05: *"R. Patel has 2
 *     jobs to send. They send under their name."*).
 *  6. **Switching technician always needs a password; biometric only returns
 *     you to your own session.** `unlockWithBiometric` refuses anyone but the
 *     technician who locked; `switchTo`/`signIn` take a password and nothing
 *     else.
 *  7. **Auto-lock after five minutes idle, and after five minutes AWAY** —
 *     amended 2026-10-26 (MQ-019, decision log; DEF-FLD-10614), PO:
 *     *"A. Lock only after 5 minutes away"*. It read *"and immediately on
 *     backgrounding"* until then. Leaving the app (Maps for Navigate, the
 *     phone for Call, the home screen) records the time; on return it locks
 *     only if the technician was away five minutes or more. A cold start
 *     still opens locked. A "background" report caused by the app's OWN
 *     system pop-up — a permission dialog, a settings screen it opened, the
 *     fingerprint prompt — never counts (`./systemInteraction.ts`).
 *
 * ⚠ ONE THING IS DELIBERATELY NOT DECIDED HERE — `OFFLINE_CAPTURE_RENEWAL`
 * below. When the capture credential has run out AND there is no signal, the
 * design says *"It asks for a password before anything more is captured"*,
 * but not whether a password alone, with no server, re-opens capture under a
 * token the server will later judge. That is a product question; the code
 * stops at it and names it.
 */
import {
  type AuthApi,
  DeviceSignedOutError,
  InvalidCredentialsError,
  OfflineError,
  type SignInResult,
} from '../security/authApi';
import { type BiometricPort, unavailableBiometric } from '../security/biometric';
import { type CaptureStamp, CaptureCredentialExpiredError, stampFromCredential } from '../security/captureStamp';
import { type Clock, MINUTE_MS } from '../security/clock';
import {
  type AccessToken,
  type CaptureCredential,
  captureExpiry,
  isAccessValid,
  isCaptureValid,
} from '../security/credentials';
import { type DeviceRegister } from '../security/deviceRegister';
import { type KeyValueStore } from '../security/prefs';
import { type SecretStore, secretKey } from '../security/secretStore';
import { type OutboxPort, type UnsentCount } from './outboxPort';
import { type PasswordVerifier } from './passwordVerifier';
import { isSystemInteractionActive, systemInteractionReturned } from './systemInteraction';

/**
 * Security tab §3 as amended 2026-10-26 (MQ-019): *five minutes idle, and five
 * minutes away*. ONE constant for both — the away limit is this one by name.
 */
export const AUTO_LOCK_IDLE_MS = 5 * MINUTE_MS;
export const AUTO_LOCK_AWAY_MS = AUTO_LOCK_IDLE_MS;

/** The question `reopenCaptureOffline` stops at. Reported for an `OQ-FLD-` id. */
export const OFFLINE_CAPTURE_RENEWAL =
  'OFFLINE_CAPTURE_RENEWAL: with the capture credential expired and no signal, does a password checked on the handset re-open capture, or does capture wait for a signal?';

export class OpenQuestionError extends Error {
  constructor(question: string) {
    super(question);
    this.name = 'OpenQuestionError';
  }
}

export class NotSignedInError extends Error {
  constructor() {
    super('nobody is signed in');
    this.name = 'NotSignedInError';
  }
}

export class LockedError extends Error {
  constructor() {
    super('the session is locked');
    this.name = 'LockedError';
  }
}

export class BiometricNotAllowedError extends Error {
  constructor() {
    super('biometric unlock only returns you to your own session');
    this.name = 'BiometricNotAllowedError';
  }
}

/** A technician this handset has seen sign in. */
export interface KnownTechnician {
  technicianId: string;
  userId: string;
  displayName: string;
  /** What they type on FF-05 ("Technician ID"). */
  login: string;
  tenant: string;
}

export type SessionPhase = 'signedOut' | 'locked' | 'unlocked';

export interface SessionSnapshot {
  phase: SessionPhase;
  /** The technician whose session this is (also while locked). */
  active: KnownTechnician | null;
  /** True while the access token is good — sending is possible. */
  canSend: boolean;
  /** True while the capture credential is good and the session is unlocked. */
  canCapture: boolean;
  /** The capture credential has run out: a password before anything more is captured. */
  captureNeedsPassword: boolean;
  /** Every technician with a session on this handset. */
  known: KnownTechnician[];
}

export interface UnsentSummary {
  /** The active technician's own unsent work. */
  mine: { items: number; photos: number };
  /** Everyone else's, under THEIR names — never added to "mine". */
  others: Array<{ technicianId: string; displayName: string; items: number; photos: number }>;
}

const PREF_KNOWN = 'handset.session.known';
const PREF_ACTIVE = 'handset.session.active';
const PREF_PHASE = 'handset.session.phase';

export interface SessionDeps {
  api: AuthApi;
  secrets: SecretStore;
  prefs: KeyValueStore;
  clock: Clock;
  device: DeviceRegister;
  verifier: PasswordVerifier;
  outbox: OutboxPort;
  biometric?: BiometricPort;
}

type Listener = (snap: SessionSnapshot) => void;

export class SessionManager {
  private known: KnownTechnician[] = [];
  private activeId: string | null = null;
  private phase: SessionPhase = 'signedOut';
  private lastActivityAt = 0;
  /** When the technician left the app (MQ-019); null while they are in it. */
  private awayAt: number | null = null;
  private readonly access = new Map<string, AccessToken>();
  private readonly capture = new Map<string, CaptureCredential>();
  private readonly listeners = new Set<Listener>();
  private readonly biometric: BiometricPort;

  constructor(private readonly deps: SessionDeps) {
    this.biometric = deps.biometric ?? unavailableBiometric;
  }

  // ── keys ────────────────────────────────────────────────────────────────
  private accessKey(id: string): string {
    return secretKey('handset', 'access', id);
  }

  private captureKey(id: string): string {
    return secretKey('handset', 'capture', id);
  }

  // ── restore ─────────────────────────────────────────────────────────────
  /**
   * On app start. A session that was open comes back LOCKED — a cold start is
   * the phone put down for an unknown time, so it is not given the five
   * minutes away that a return from the background is (MQ-019).
   */
  async restore(): Promise<SessionSnapshot> {
    const rawKnown = this.deps.prefs.getString(PREF_KNOWN);
    this.known = rawKnown ? (JSON.parse(rawKnown) as KnownTechnician[]) : [];
    for (const t of this.known) {
      const a = await this.deps.secrets.get(this.accessKey(t.technicianId));
      if (a) this.access.set(t.technicianId, JSON.parse(a) as AccessToken);
      const c = await this.deps.secrets.get(this.captureKey(t.technicianId));
      if (c) this.capture.set(t.technicianId, JSON.parse(c) as CaptureCredential);
    }
    const active = this.deps.prefs.getString(PREF_ACTIVE) ?? null;
    this.activeId = active && this.known.some((k) => k.technicianId === active) ? active : null;
    this.phase = this.activeId ? 'locked' : 'signedOut';
    this.persistPointer();
    return this.emit();
  }

  // ── reading ─────────────────────────────────────────────────────────────
  snapshot(): SessionSnapshot {
    const now = this.deps.clock.now();
    const active = this.activeTechnician();
    const cred = active ? this.capture.get(active.technicianId) : undefined;
    const captureValid = isCaptureValid(cred, now);
    return {
      phase: this.phase,
      active,
      canSend: active != null && isAccessValid(this.access.get(active.technicianId), now),
      canCapture: this.phase === 'unlocked' && captureValid,
      captureNeedsPassword: active != null && !captureValid,
      known: [...this.known],
    };
  }

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(): SessionSnapshot {
    const snap = this.snapshot();
    for (const l of this.listeners) l(snap);
    return snap;
  }

  private activeTechnician(): KnownTechnician | null {
    return this.known.find((k) => k.technicianId === this.activeId) ?? null;
  }

  /** The capture credential this technician holds on this handset, if any. */
  captureCredentialOf(technicianId: string): CaptureCredential | null {
    return this.capture.get(technicianId) ?? null;
  }

  /** Whether this technician's capture credential is held AND still good — their items can travel (Security §3). */
  captureValid(technicianId: string): boolean {
    return isCaptureValid(this.capture.get(technicianId), this.deps.clock.now());
  }

  /**
   * DEF-FLD-10629 (FB-004, G): a sync asks for a fresh capture credential for
   * the SIGNED-IN technician when theirs is missing or expired, before
   * sending. Until this the only renewal was at sign-in and refresh, and a
   * failure there was silent — so a reader's whole route waited, unshown,
   * while the pull (the access token) went on working. True when renewed.
   */
  async renewCaptureNow(): Promise<boolean> {
    const tech = this.activeTechnician();
    if (!tech || this.phase === 'signedOut') return false;
    const ok = await this.renewCapture(tech);
    if (ok) this.emit();
    return ok;
  }

  // ── signing in, and switching (always a password) ───────────────────────
  /**
   * FF-05 sign-in, and *Switch technician → Hand over*. Always a password.
   *
   * Online: the server checks it, issues a fresh access token and capture
   * credential, and the handset remembers a verifier for offline unlocks.
   * Offline: a technician who has signed in on THIS handset before is checked
   * against that verifier and resumes with whatever credentials they still
   * hold — capture if the capture credential is good, sending at the next
   * signal. A technician the handset has never seen cannot sign in offline.
   */
  async signIn(input: { tenant: string; login: string; password: string }): Promise<SessionSnapshot> {
    const deviceId = await this.deps.device.deviceId();
    let result: SignInResult;
    try {
      result = await this.deps.api.signIn({ ...input, deviceId });
    } catch (err) {
      if (err instanceof OfflineError) return this.signInOffline(input, err);
      throw err;
    }
    const now = this.deps.clock.now();
    const tech: KnownTechnician = {
      technicianId: result.technician.id,
      userId: result.user.id,
      displayName: result.technician.displayName || result.user.displayName,
      login: input.login,
      tenant: input.tenant,
    };
    this.upsertKnown(tech);
    await this.setAccess(tech.technicianId, {
      token: result.access.token,
      expiresAt: now + result.access.expiresInSeconds * 1000,
      refreshToken: result.access.refreshToken ?? null,
    });
    await this.deps.verifier.remember(tech.technicianId, input.password);
    await this.renewCapture(tech);
    this.activate(tech.technicianId);
    return this.emit();
  }

  private async signInOffline(input: { tenant: string; login: string; password: string }, why: OfflineError): Promise<SessionSnapshot> {
    const tech = this.known.find((k) => k.login === input.login && k.tenant === input.tenant);
    // The ORIGINAL error, so a refused certificate or an outdated server keeps
    // its own words rather than reading as "No signal" (DEF-FLD-10617).
    if (!tech) throw why;
    const ok = await this.deps.verifier.check(tech.technicianId, input.password);
    if (!ok) throw new InvalidCredentialsError();
    this.activate(tech.technicianId);
    return this.emit();
  }

  /** Hand the phone to someone already known on it — a password, never a thumb. */
  async switchTo(technicianId: string, password: string): Promise<SessionSnapshot> {
    const tech = this.known.find((k) => k.technicianId === technicianId);
    if (!tech) throw new NotSignedInError();
    return this.signIn({ tenant: tech.tenant, login: tech.login, password });
  }

  private activate(technicianId: string): void {
    this.activeId = technicianId;
    this.phase = 'unlocked';
    this.lastActivityAt = this.deps.clock.now();
    this.awayAt = null;
    this.persistPointer();
  }

  private upsertKnown(tech: KnownTechnician): void {
    const i = this.known.findIndex((k) => k.technicianId === tech.technicianId);
    if (i >= 0) this.known[i] = tech;
    else this.known.push(tech);
    this.deps.prefs.set(PREF_KNOWN, JSON.stringify(this.known));
  }

  private persistPointer(): void {
    if (this.activeId) this.deps.prefs.set(PREF_ACTIVE, this.activeId);
    else this.deps.prefs.delete(PREF_ACTIVE);
    this.deps.prefs.set(PREF_PHASE, this.phase);
  }

  private async setAccess(technicianId: string, token: AccessToken): Promise<void> {
    this.access.set(technicianId, token);
    await this.deps.secrets.set(this.accessKey(technicianId), JSON.stringify(token));
  }

  private async clearAccess(technicianId: string): Promise<void> {
    this.access.delete(technicianId);
    await this.deps.secrets.remove(this.accessKey(technicianId));
  }

  /**
   * *"renewed on every successful contact"*. A failure to renew is not a
   * failure to sign in: the old credential, if still good, carries on.
   */
  private async renewCapture(tech: KnownTechnician): Promise<boolean> {
    const token = this.access.get(tech.technicianId);
    if (!token) return false;
    const deviceId = await this.deps.device.deviceId();
    const deviceName = (await this.deps.device.deviceName()) ?? '';
    try {
      const issued = await this.deps.api.issueCaptureToken({
        tenant: tech.tenant,
        accessToken: token.token,
        deviceName,
        deviceId,
      });
      const now = this.deps.clock.now();
      const cred: CaptureCredential = {
        technicianId: tech.technicianId,
        userId: tech.userId,
        tenant: tech.tenant,
        deviceId,
        serverToken: issued.captureToken,
        issuedAt: now,
        expiresAt: captureExpiry(now, issued.maxAgeSeconds, issued.expiresAt),
      };
      this.capture.set(tech.technicianId, cred);
      await this.deps.secrets.set(this.captureKey(tech.technicianId), JSON.stringify(cred));
      return true;
    } catch (err) {
      if (err instanceof DeviceSignedOutError) {
        await this.remoteSignOut(tech.technicianId);
      }
      return false;
    }
  }

  // ── refreshing (only ever with a signal) ────────────────────────────────
  /**
   * A new access token and a renewed capture credential for the active
   * technician. Offline is normal and uneventful: nothing changes, capture
   * carries on, sending waits.
   */
  async refresh(): Promise<SessionSnapshot> {
    const tech = this.activeTechnician();
    if (!tech) return this.snapshot();
    const token = this.access.get(tech.technicianId);
    if (!token) return this.snapshot();
    const deviceId = await this.deps.device.deviceId();
    try {
      const access = await this.deps.api.refreshAccess({
        tenant: tech.tenant,
        accessToken: token.token,
        refreshToken: token.refreshToken ?? null,
        deviceId,
      });
      // The refresh token is single use and rotated: keep the new one.
      await this.setAccess(tech.technicianId, {
        token: access.token,
        expiresAt: this.deps.clock.now() + access.expiresInSeconds * 1000,
        refreshToken: access.refreshToken ?? token.refreshToken ?? null,
      });
      await this.renewCapture(tech);
    } catch (err) {
      if (err instanceof DeviceSignedOutError) {
        await this.remoteSignOut(tech.technicianId);
      } else if (!(err instanceof OfflineError) && !(err instanceof InvalidCredentialsError)) {
        // A refresh token the server no longer takes (expired, revoked) is
        // not an error to throw at a screen: sending waits for a password,
        // capture carries on while its credential is good.
        throw err;
      }
    }
    return this.emit();
  }

  /** The access token a send may travel under — whoever is signed in is the courier. */
  courierAccessToken(): string | null {
    const tech = this.activeTechnician();
    if (!tech || this.phase === 'signedOut') return null;
    const token = this.access.get(tech.technicianId);
    return isAccessValid(token, this.deps.clock.now()) ? (token as AccessToken).token : null;
  }

  // ── capture ─────────────────────────────────────────────────────────────
  /**
   * The stamp for an item being captured NOW by the active technician. It
   * comes from their capture credential — the session is consulted only to
   * know whose hand is on the phone and that it is unlocked.
   */
  stampCapture(): CaptureStamp {
    const tech = this.activeTechnician();
    if (!tech || this.phase === 'signedOut') throw new NotSignedInError();
    if (this.phase === 'locked') throw new LockedError();
    const cred = this.capture.get(tech.technicianId);
    if (!cred) throw new CaptureCredentialExpiredError(tech.technicianId);
    return stampFromCredential(cred, this.deps.clock.now());
  }

  /**
   * The capture credential has run out and there is no signal. Stops at the
   * open question rather than choosing (CLAUDE.md, prime directive).
   */
  async reopenCaptureOffline(_password: string): Promise<never> {
    throw new OpenQuestionError(OFFLINE_CAPTURE_RENEWAL);
  }

  // ── locking ─────────────────────────────────────────────────────────────
  /** Any touch. */
  touch(): void {
    if (this.phase === 'unlocked') this.lastActivityAt = this.deps.clock.now();
  }

  /**
   * Called on a timer; locks after five minutes with no touch. While the
   * technician is AWAY the idle clock does not run (a timer can still fire in
   * the background on Android) — time away is judged by `onForeground`.
   */
  tick(): SessionSnapshot {
    if (
      this.phase === 'unlocked' &&
      this.awayAt === null &&
      this.deps.clock.now() - this.lastActivityAt >= AUTO_LOCK_IDLE_MS
    ) {
      return this.lock();
    }
    return this.snapshot();
  }

  /**
   * The platform says the app left the foreground (`background` or
   * `inactive`). Records WHEN — it locks nothing (MQ-019). Ignored entirely
   * while the app's own system pop-up is up: Android reports a permission
   * dialog as backgrounding. A second report while already away (iOS sends
   * `inactive` then `background`) keeps the first time.
   */
  onBackground(): SessionSnapshot {
    if (this.phase !== 'unlocked' || isSystemInteractionActive()) return this.snapshot();
    if (this.awayAt === null) this.awayAt = this.deps.clock.now();
    return this.snapshot();
  }

  /**
   * The app is active again. Away five minutes or more → locked. Less → still
   * unlocked, and the return counts as a touch, so idle time BEFORE leaving
   * does not lock the moment the technician comes back from a short call.
   */
  onForeground(): SessionSnapshot {
    systemInteractionReturned();
    const awayAt = this.awayAt;
    this.awayAt = null;
    if (this.phase !== 'unlocked' || awayAt === null) return this.snapshot();
    const now = this.deps.clock.now();
    if (now - awayAt >= AUTO_LOCK_AWAY_MS) return this.lock();
    this.lastActivityAt = now;
    return this.emit();
  }

  lock(): SessionSnapshot {
    if (this.phase === 'unlocked') {
      this.phase = 'locked';
      this.persistPointer();
    }
    return this.emit();
  }

  /** Back into your OWN session with your password — works offline. */
  async unlockWithPassword(password: string): Promise<SessionSnapshot> {
    const tech = this.activeTechnician();
    if (!tech) throw new NotSignedInError();
    const ok = await this.deps.verifier.check(tech.technicianId, password);
    if (ok === null) {
      // Never signed in on this handset with a verifier — ask the server.
      return this.signIn({ tenant: tech.tenant, login: tech.login, password });
    }
    if (!ok) throw new InvalidCredentialsError();
    this.activate(tech.technicianId);
    return this.emit();
  }

  /**
   * Back into your OWN session with a thumb. Only the technician whose session
   * is locked; anyone else is a switch, and a switch is a password.
   */
  async unlockWithBiometric(asTechnicianId: string, prompt: string): Promise<SessionSnapshot> {
    const tech = this.activeTechnician();
    if (!tech || this.phase !== 'locked') throw new NotSignedInError();
    if (asTechnicianId !== tech.technicianId) throw new BiometricNotAllowedError();
    if (!(await this.biometric.isAvailable())) throw new BiometricNotAllowedError();
    if (!(await this.biometric.authenticate(prompt))) throw new InvalidCredentialsError();
    this.activate(tech.technicianId);
    return this.emit();
  }

  // ── signing out ─────────────────────────────────────────────────────────
  /**
   * FF-53 *Sign out anyway*. Ends this technician's session on the handset.
   * Deletes NOTHING they captured: their unsent work stays and sends under
   * their name at the next signal (R64). Their capture credential stays in
   * the keystore, behind their password, so signing back in on a job with no
   * signal still lets them work.
   */
  async signOut(): Promise<SessionSnapshot> {
    const tech = this.activeTechnician();
    if (!tech) return this.snapshot();
    const token = this.access.get(tech.technicianId);
    if (token) {
      try {
        await this.deps.api.signOut({ tenant: tech.tenant, accessToken: token.token });
      } catch {
        // No signal, or the server cannot revoke yet. Signing out on the
        // handset never waits on the server.
      }
    }
    await this.clearAccess(tech.technicianId);
    this.activeId = null;
    this.phase = 'signedOut';
    this.persistPointer();
    return this.emit();
  }

  /**
   * The office signed this handset out (Security tab §4, R115). The MIRROR
   * goes; the outbox and its photo files do not — they send, then go.
   */
  async remoteSignOut(technicianId: string): Promise<SessionSnapshot> {
    await this.deps.outbox.dropMirror(technicianId);
    await this.clearAccess(technicianId);
    this.capture.delete(technicianId);
    await this.deps.secrets.remove(this.captureKey(technicianId));
    await this.deps.verifier.forget(technicianId);
    if (this.activeId === technicianId) {
      this.activeId = null;
      this.phase = 'signedOut';
      this.persistPointer();
    }
    return this.emit();
  }

  // ── what is waiting ─────────────────────────────────────────────────────
  /**
   * Mine and others', never merged. With nobody signed in (FF-05), everyone's
   * is "others".
   */
  async unsentSummary(): Promise<UnsentSummary> {
    const counts: UnsentCount[] = await this.deps.outbox.unsentCounts();
    const mine = { items: 0, photos: 0 };
    const others: UnsentSummary['others'] = [];
    const activeId = this.phase === 'signedOut' ? null : this.activeId;
    for (const c of counts) {
      if (c.items === 0 && c.photos === 0) continue;
      if (c.technicianId === activeId) {
        mine.items += c.items;
        mine.photos += c.photos;
      } else {
        const who = this.known.find((k) => k.technicianId === c.technicianId);
        others.push({
          technicianId: c.technicianId,
          // A technician whose session was cleared remotely is still named on
          // their own work; an unknown owner is never relabelled as the viewer.
          displayName: who?.displayName ?? '',
          items: c.items,
          photos: c.photos,
        });
      }
    }
    return { mine, others };
  }
}
