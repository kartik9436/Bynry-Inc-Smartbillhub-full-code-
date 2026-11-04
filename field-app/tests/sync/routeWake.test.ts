/**
 * DEF-MET-10606 — a route given or taken away: the server's `route_change`
 * push downloads the routes and shows ONE worded line, in the technician's
 * language, only for the utility signed in.
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import * as Notifications from 'expo-notifications';

import { listenForPushes, routeChangeHandler, showPushesInForeground } from '../../src/device/native/notifications';
import { isRouteChangePush, onRouteWake, routeChangeText, wakeRoutes } from '../../src/sync/routeWake';

const N = Notifications as jest.Mocked<typeof Notifications>;
beforeEach(() => jest.clearAllMocks());

const en = JSON.parse(readFileSync(resolve(__dirname, '../../../07-frontend/src/i18n/locales/en.json'), 'utf8')) as Record<string, string>;
const t = (key: string, opts: Record<string, unknown> = {}) =>
  (en[key] ?? `«${key}»`).replace(/\{\{(\w+)\}\}/g, (_, k: string) => String(opts[k] ?? ''));

const push = (data: Record<string, unknown>) => ({ kind: 'route_change', tenant: 'silver-creek', ...data });

describe('the words', () => {
  test('one route gained, with its name', () => {
    expect(routeChangeText(push({ gained: '1', lost: '0', route: 'RT-001', route_name: 'Silver Creek' }), t)).toBe('New route: RT-001 · Silver Creek');
  });
  test('one route gained, no name', () => {
    expect(routeChangeText(push({ gained: '1', lost: '0', route: 'RT-001' }), t)).toBe('New route: RT-001');
  });
  test('a bulk of five is one line', () => {
    expect(routeChangeText(push({ gained: '5', lost: '0' }), t)).toBe('5 new routes');
  });
  test('one route taken away', () => {
    expect(routeChangeText(push({ gained: '0', lost: '1', route: 'RT-002' }), t)).toBe('Route removed: RT-002');
  });
  test('three taken away', () => {
    expect(routeChangeText(push({ gained: '0', lost: '3' }), t)).toBe('3 routes removed');
  });
  test('a push naming nothing has no words', () => {
    expect(routeChangeText(push({ gained: '0', lost: '0' }), t)).toBeNull();
  });
  test('every word is in all eleven catalogues', () => {
    const keys = ['field.ff52.routeChanges', 'field.push.routes.newOneNamed', 'field.push.routes.newOne', 'field.push.routes.newMany', 'field.push.routes.removedOne', 'field.push.routes.removedMany'];
    for (const code of ['en', 'de', 'es', 'es-MX', 'fr-FR', 'hi', 'id-ID', 'it-IT', 'ja-JP', 'ko-KR', 'pt-BR']) {
      const cat = JSON.parse(readFileSync(resolve(__dirname, `../../../07-frontend/src/i18n/locales/${code}.json`), 'utf8')) as Record<string, string>;
      for (const k of keys) expect([code, k, !!cat[k]]).toEqual([code, k, true]);
    }
  });
});

describe('the push wakes the route download', () => {
  test('a route-change push wakes every listener; the handset\'s own copy does not', () => {
    const heard = jest.fn();
    const stop = onRouteWake(heard);
    const present = jest.fn(async () => undefined);
    const handle = routeChangeHandler(t, present);
    handle(push({ gained: '1', lost: '0', route: 'RT-001', route_name: 'Silver Creek' }), 'received');
    expect(heard).toHaveBeenCalledTimes(1);
    expect(present).toHaveBeenCalledWith('New route: RT-001 · Silver Creek', expect.objectContaining({ handset: '1', tenant: 'silver-creek' }));
    // The worded copy arrives back through the same listener: nothing happens twice.
    handle({ ...(present.mock.calls[0] as unknown[])[1] as Record<string, unknown> }, 'received');
    expect(heard).toHaveBeenCalledTimes(1);
    expect(present).toHaveBeenCalledTimes(1);
    stop();
  });

  test('a TAPPED push downloads but does not show the line again', () => {
    const heard = jest.fn();
    const stop = onRouteWake(heard);
    const present = jest.fn(async () => undefined);
    routeChangeHandler(t, present)(push({ gained: '0', lost: '1', route: 'RT-002' }), 'tapped');
    expect(heard).toHaveBeenCalledTimes(1);
    expect(present).not.toHaveBeenCalled();
    stop();
  });

  test('a job push wakes no route download', () => {
    const heard = jest.fn();
    const stop = onRouteWake(heard);
    routeChangeHandler(t, jest.fn(async () => undefined))({ kind: 'new_job', tenant: 'silver-creek' }, 'received');
    expect(heard).not.toHaveBeenCalled();
    expect(isRouteChangePush({ kind: 'new_job' })).toBe(false);
    stop();
  });

  test('ANOTHER utility\'s route push never reaches the handler', () => {
    const session = {
      snapshot: () => ({ phase: 'unlocked', active: { tenant: 'silver-creek' } }) as never,
    };
    const onOurs = jest.fn();
    listenForPushes(session, onOurs);
    const received = N.addNotificationReceivedListener.mock.calls[0]![0];
    received({ request: { content: { data: push({ tenant: 'oak-valley', gained: '1' }) } } } as never);
    expect(onOurs).not.toHaveBeenCalled();
    received({ request: { content: { data: push({ gained: '1' }) } } } as never);
    expect(onOurs).toHaveBeenCalledWith(expect.objectContaining({ kind: 'route_change' }), 'received');
  });

  test('in the foreground the server\'s wordless copy is silent and the handset\'s worded one shows', async () => {
    const session = { snapshot: () => ({ phase: 'unlocked', active: { tenant: 'silver-creek' } }) as never };
    showPushesInForeground(session);
    const handler = N.setNotificationHandler.mock.calls[0]![0]!;
    const show = (data: Record<string, unknown>) => handler.handleNotification({ request: { content: { data } } } as never);
    await expect(show(push({ gained: '1' }))).resolves.toMatchObject({ shouldShowBanner: false });
    await expect(show(push({ gained: '1', handset: '1' }))).resolves.toMatchObject({ shouldShowBanner: true });
  });

  test('a listener that throws never stops the others', () => {
    const second = jest.fn();
    const a = onRouteWake(() => {
      throw new Error('no store');
    });
    const b = onRouteWake(second);
    expect(wakeRoutes(push({ gained: '1' }))).toBe(1);
    expect(second).toHaveBeenCalled();
    a();
    b();
  });
});
