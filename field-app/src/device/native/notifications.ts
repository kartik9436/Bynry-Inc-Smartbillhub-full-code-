/**
 * Notifications on the handset: the Android CHANNELS the server's pushes
 * arrive on, the permission (with iOS Critical Alerts for an emergency), and
 * the device PUSH TOKEN registered through the existing devices route.
 *
 * THE SIX KINDS ARE THE SERVER'S (`06-backend/apps/work/push.py`
 * `PUSH_KINDS`): the channel id and the importance are copied from there, and
 * `tests/device/native/notifications.test.ts` reads that file and fails if the
 * two drift — a push naming a channel the handset never created falls into
 * Android's fallback channel, silently, at the wrong importance.
 *
 * ⚠ **ANDROID FIXES A CHANNEL'S SOUND THE FIRST TIME THE CHANNEL IS CREATED.**
 * The server names a sound per kind (`new_job.wav`, `emergency.wav` …) and no
 * sound file exists in this repo yet, so the channels are created with the
 * platform's default sound. Once a handset has a channel, changing its sound
 * needs a NEW channel id, which the server would then have to send. So the
 * five `.wav` files must be added (`expo-notifications` plugin `sounds`, and
 * `CHANNEL_SOUND` below) BEFORE the first build reaches a technician — after
 * that it is a channel rename on both sides.
 *
 * ⚠ **AN EMERGENCY MUST BREAK THROUGH SILENT MODE (ADR-012, R28).** Android:
 * the `emergency` channel is MAX importance and asks to bypass Do Not
 * Disturb (the technician grants that in the channel's settings). iOS: the
 * permission request asks for Critical Alerts, which the app's entitlement
 * allows (PO 2026-10-21, *"we have taken this permission"*); the server sends
 * `interruption_level: critical`.
 *
 * THE TOKEN IS A BEARER CREDENTIAL FOR A THIRD PARTY. It is sent to our
 * server and nowhere else, never logged, never shown, never stored by us.
 */
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import type { AuthApi } from '../../security/authApi';
import type { SessionManager, SessionSnapshot } from '../../session/sessionManager';
import { isRouteChangePush, ROUTE_CHANGE_KIND, routeChangeText, wakeRoutes } from '../../sync/routeWake';

/** `push.py` PUSH_KINDS, one row per kind: the Android channel and its importance. */
export const PUSH_CHANNELS = [
  { kind: 'new_job', importance: 'default', label: 'field.ff52.newJob' },
  { kind: 'urgent_assignment', importance: 'high', label: 'field.ff42.kind.urgent' },
  { kind: 'emergency', importance: 'max', label: 'field.ff42.kind.emergency' },
  { kind: 'schedule_change', importance: 'high', label: 'field.ff42.kind.schedule' },
  { kind: 'dispatch_message', importance: 'low', label: 'field.ff52.dispatchMessages' },
  // DEF-MET-10606 — a meter-reading route given or taken away (`routeWake.ts`).
  { kind: 'route_change', importance: 'default', label: 'field.ff52.routeChanges' },
] as const;

export type PushKind = (typeof PUSH_CHANNELS)[number]['kind'];
export type ChannelImportance = (typeof PUSH_CHANNELS)[number]['importance'];

/**
 * The sound file per kind, once the files exist (see the header). `null` is
 * the platform default — what every channel uses until they are supplied.
 */
export const CHANNEL_SOUND: Record<PushKind, string | null> = {
  new_job: null,
  urgent_assignment: null,
  emergency: null,
  schedule_change: null,
  dispatch_message: null,
  route_change: null,
};

export function androidImportance(level: ChannelImportance): Notifications.AndroidImportance {
  switch (level) {
    case 'max':
      return Notifications.AndroidImportance.MAX;
    case 'high':
      return Notifications.AndroidImportance.HIGH;
    case 'low':
      return Notifications.AndroidImportance.LOW;
    default:
      return Notifications.AndroidImportance.DEFAULT;
  }
}

/** Create (or refresh the name of) the six channels. Android only; a no-op elsewhere. */
export async function ensurePushChannels(t: (key: string) => string, os: string = Platform.OS): Promise<number> {
  if (os !== 'android') return 0;
  for (const c of PUSH_CHANNELS) {
    const emergency = c.kind === 'emergency';
    await Notifications.setNotificationChannelAsync(c.kind, {
      name: t(c.label),
      importance: androidImportance(c.importance),
      sound: CHANNEL_SOUND[c.kind] ?? 'default',
      enableVibrate: true,
      bypassDnd: emergency,
      lockscreenVisibility: Notifications.AndroidNotificationVisibility.PUBLIC,
    });
  }
  return PUSH_CHANNELS.length;
}

/** The iOS ask: alerts, badge, sound — and Critical Alerts for an emergency. */
export const IOS_PERMISSION_REQUEST = {
  ios: { allowAlert: true, allowBadge: true, allowSound: true, allowCriticalAlerts: true },
} as const;

export async function notificationsAllowed(): Promise<boolean> {
  try {
    return (await Notifications.getPermissionsAsync()).granted;
  } catch {
    return false;
  }
}

/** While the app is open, a push still shows and sounds (an emergency must never be quiet). */
/**
 * ⚠ **A PUSH IS ACTED ON ONLY FOR THE UTILITY THE APP IS SIGNED INTO
 * (`DEF-WRK-10352`).** A technician may work for two utilities on one phone,
 * signed into one at a time; a push for the other one, or for anybody while
 * nobody is signed in, gets NO banner, NO sound, NO navigation and opens NO
 * database — nothing at all.
 *
 * The push's utility is `data.tenant` (the tenant's slug, the same string the
 * session holds). ⚠ **THE SERVER DOES NOT SEND IT YET** — `push.py`
 * `push_message` carries `kind`, `alert_id`, `work_order_id`, `order_no` and
 * no tenant. Until it does, NO push can be shown as ours, so this fails CLOSED
 * and every push is ignored in the app (the next sync still delivers the job;
 * the push is the doorbell, not the parcel). What happens while the app is in
 * the BACKGROUND is the operating system's, not this handler's — which is why
 * the server must also stop pushing to a token after sign-out.
 */
export type PushSession = Pick<SessionManager, 'snapshot'>;

export function pushTenant(data: unknown): string | null {
  const t = (data as { tenant?: unknown } | null | undefined)?.tenant;
  return typeof t === 'string' && t.trim() !== '' ? t.trim() : null;
}

/** True only when somebody is signed in and the push names THEIR utility. */
export function pushIsForThisSession(data: unknown, session: PushSession): boolean {
  const snap = session.snapshot();
  const tenant = pushTenant(data);
  if (snap.phase === 'signedOut' || !snap.active || !tenant) return false;
  return snap.active.tenant === tenant;
}

const SILENT = { shouldShowBanner: false, shouldShowList: false, shouldPlaySound: false, shouldSetBadge: false } as const;

/** While the app is open, OUR push still shows and sounds (an emergency must never be quiet); anyone else's does nothing. */
export function showPushesInForeground(session: PushSession): void {
  Notifications.setNotificationHandler({
    handleNotification: async (notification) =>
      pushIsForThisSession(notification?.request?.content?.data, session)
        ? isRouteChangePush(notification?.request?.content?.data as Record<string, unknown> | undefined)
          ? // The server's copy carries no words; the handset posts its own worded one (`announceRouteChange`).
            SILENT
          : { shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: true }
        : SILENT,
  });
}

/**
 * OUR utility's route-change push (DEF-MET-10606): download the routes
 * (`routeWake.ts`) and, when it ARRIVED (not when it was tapped — the
 * technician has already seen it), show the one worded line in their
 * language on the `route_change` channel. The worded copy is marked
 * `handset: '1'` so it never wakes anything a second time.
 */
export function routeChangeHandler(
  t: (key: string, opts?: Record<string, unknown>) => string,
  present: (title: string, data: Record<string, unknown>) => Promise<unknown> = presentLocally,
): (data: Record<string, unknown>, how: 'received' | 'tapped') => void {
  return (data, how) => {
    if (!isRouteChangePush(data)) return;
    wakeRoutes(data);
    if (how !== 'received') return;
    const title = routeChangeText(data, t);
    if (title) void present(title, { ...data, handset: '1' }).catch(() => undefined);
  };
}

function presentLocally(title: string, data: Record<string, unknown>): Promise<unknown> {
  return Notifications.scheduleNotificationAsync({
    content: { title, data },
    trigger: Platform.OS === 'android' ? { channelId: ROUTE_CHANGE_KIND } : null,
  });
}

/**
 * The one door from a push into the app: `onOurs` is called only for a push
 * (received, or tapped) that belongs to the signed-in utility, with which of
 * the two it was. `NativeApp` passes `routeChangeHandler` (DEF-MET-10606);
 * any other kind opens the app where it is and the sync brings the job, and
 * whatever is wired here later inherits the guard. Returns the unsubscribe.
 */
export function listenForPushes(
  session: PushSession,
  onOurs: (data: Record<string, unknown>, how: 'received' | 'tapped') => void = () => undefined,
): () => void {
  const guard = (data: unknown, how: 'received' | 'tapped') => {
    if (pushIsForThisSession(data, session)) onOurs(data as Record<string, unknown>, how);
  };
  const received = Notifications.addNotificationReceivedListener((n) => guard(n?.request?.content?.data, 'received'));
  const tapped = Notifications.addNotificationResponseReceivedListener((r) => guard(r?.notification?.request?.content?.data, 'tapped'));
  return () => {
    received.remove();
    tapped.remove();
  };
}

export type PushPlatform = 'ios' | 'android';

export interface PushRegistrarDeps {
  session: Pick<SessionManager, 'snapshot' | 'subscribe' | 'courierAccessToken'>;
  api: Pick<AuthApi, 'registerDevice'>;
  deviceId: () => Promise<string>;
  deviceName: () => Promise<string | null>;
  /** The platform's push token (FCM on Android, APNs on iOS); null when there is none. */
  pushToken?: () => Promise<string | null>;
  allowed?: () => Promise<boolean>;
}

/** The native push token: FCM on Android, APNs on iOS. Null on a simulator or without permission. */
export async function devicePushToken(): Promise<string | null> {
  try {
    const token = await Notifications.getDevicePushTokenAsync();
    return typeof token.data === 'string' && token.data ? token.data : null;
  } catch {
    return null;
  }
}

/**
 * Registers the push token for whoever is signed in, once per (technician,
 * token). The server moves a token to the technician who registers it
 * (`BR-WRK-059`), so after a switch the tablet rings for the new technician.
 * Offline or refused: tried again on the next session change or `tryNow()`.
 */
export function createPushRegistrar(deps: PushRegistrarDeps): { tryNow(): Promise<boolean>; stop(): void } {
  const pushToken = deps.pushToken ?? devicePushToken;
  const allowed = deps.allowed ?? notificationsAllowed;
  let done: string | null = null;
  let running: Promise<boolean> | null = null;

  const attempt = async (snap: SessionSnapshot): Promise<boolean> => {
    const tech = snap.phase === 'signedOut' ? null : snap.active;
    const accessToken = deps.session.courierAccessToken();
    if (!tech || !accessToken || !(await allowed())) return false;
    const token = await pushToken();
    if (!token) return false;
    const key = `${tech.tenant}|${tech.technicianId}|${token}`;
    if (done === key) return true;
    try {
      await deps.api.registerDevice({
        tenant: tech.tenant,
        accessToken,
        deviceId: await deps.deviceId(),
        name: (await deps.deviceName()) ?? '',
        pushToken: token,
      });
      done = key;
      return true;
    } catch {
      return false;
    }
  };

  const tryNow = () => {
    if (!running) running = attempt(deps.session.snapshot()).finally(() => (running = null));
    return running;
  };
  const unsubscribe = deps.session.subscribe(() => void tryNow());
  return { tryNow, stop: unsubscribe };
}
