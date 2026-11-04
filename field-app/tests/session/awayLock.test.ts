/**
 * MQ-019 (decision log 2026-10-26, PO: *"A. Lock only after 5 minutes away"*;
 * DEF-FLD-10614). The app locks after five minutes IDLE and after five
 * minutes AWAY — never the instant it is backgrounded — and a "background"
 * report caused by the app's OWN system pop-up never counts as leaving.
 *
 * Why this file exists: the old tests modelled backgrounding only as the
 * technician leaving. Android reports its own permission dialog as
 * backgrounding, so answering *Don't allow* locked the app mid-job.
 */
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

import { MINUTE_MS } from '../../src/security/clock';
import { AUTO_LOCK_AWAY_MS, AUTO_LOCK_IDLE_MS } from '../../src/session/sessionManager';
import {
  isSystemInteractionActive,
  resetSystemInteractionForTests,
  withSystemInteraction,
} from '../../src/session/systemInteraction';
import { makeHandset, signIn } from './fakes';

afterEach(() => resetSystemInteractionForTests());

test('one constant: away and idle are the same five minutes', () => {
  expect(AUTO_LOCK_AWAY_MS).toBe(AUTO_LOCK_IDLE_MS);
  expect(AUTO_LOCK_IDLE_MS).toBe(5 * MINUTE_MS);
});

test("the app's own permission dialog: background then active leaves it unlocked", async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  let answer!: (v: string) => void;
  const asked = withSystemInteraction(() => new Promise<string>((r) => (answer = r)));
  expect(isSystemInteractionActive()).toBe(true);
  // Android reports the dialog as the app going to the background.
  expect(h.session.onBackground().phase).toBe('unlocked');
  // The technician reads the dialog for six minutes and taps Don't allow.
  h.clock.advance(6 * MINUTE_MS);
  answer('denied');
  await asked;
  expect(isSystemInteractionActive()).toBe(false);
  expect(h.session.onForeground().phase).toBe('unlocked');
});

test('a settings screen the app opened never counts, even after it resolves', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  // Linking.openSettings resolves as soon as the settings screen is launched,
  // BEFORE the platform reports the background — so the guard holds until return.
  await withSystemInteraction(async () => undefined, { untilReturn: true });
  expect(h.session.onBackground().phase).toBe('unlocked');
  h.clock.advance(6 * MINUTE_MS);
  expect(h.session.onForeground().phase).toBe('unlocked');
  // Returning cleared the guard: the next real leave counts.
  expect(isSystemInteractionActive()).toBe(false);
  h.session.onBackground();
  h.clock.advance(6 * MINUTE_MS);
  expect(h.session.onForeground().phase).toBe('locked');
});

test('a failed system call releases the guard', async () => {
  await expect(
    withSystemInteraction(async () => {
      throw new Error('no settings');
    }, { untilReturn: true }),
  ).rejects.toThrow('no settings');
  expect(isSystemInteractionActive()).toBe(false);
});

test('away two minutes (a customer call): still unlocked on return', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  expect(h.session.onBackground().phase).toBe('unlocked');
  h.clock.advance(2 * MINUTE_MS);
  h.session.tick(); // a timer that fires while away does not lock
  expect(h.session.onForeground().phase).toBe('unlocked');
});

test('away six minutes (Maps for Navigate): locked on return', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  h.session.onBackground();
  h.clock.advance(6 * MINUTE_MS);
  expect(h.session.onForeground().phase).toBe('locked');
});

test('away exactly five minutes locks; inactive then background measures from the first report', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  h.session.onBackground(); // inactive
  h.clock.advance(1 * MINUTE_MS);
  h.session.onBackground(); // background — does not restart the clock
  h.clock.advance(4 * MINUTE_MS);
  expect(h.session.onForeground().phase).toBe('locked');
});

test('returning counts as a touch: idle before leaving does not lock the moment you return', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  h.clock.advance(4 * MINUTE_MS); // idle four minutes
  h.session.onBackground();
  h.clock.advance(2 * MINUTE_MS); // a two-minute call
  h.session.onForeground();
  expect(h.session.tick().phase).toBe('unlocked');
});

test('idle five minutes in the app still locks (unchanged)', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  h.clock.advance(AUTO_LOCK_IDLE_MS);
  expect(h.session.tick().phase).toBe('locked');
});

test('a cold start still opens locked (unchanged)', async () => {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const snap = await h.build().restore();
  expect(snap.phase).toBe('locked');
});

describe('every place the app asks the platform for something is inside the guard', () => {
  // A new permission request, settings visit or system prompt added WITHOUT
  // the guard would lock the app mid-job again and every behaviour test above
  // would stay green — so the source is read. A call counts as guarded when
  // `withSystemInteraction(` opens on its own line or the eight before it (a switch inside one wrapper).
  const SYSTEM_CALL = /request\w*Permissions?\w*\(|Linking\.openSettings\(|authenticateAsync\(|getDocumentAsync\(|enableNetworkProviderAsync\(|\brequest\(\)/;
  const root = join(__dirname, '../../src');
  const files: string[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const p = join(dir, name);
      if (statSync(p).isDirectory()) walk(p);
      else if (/\.tsx?$/.test(name)) files.push(p);
    }
  };
  walk(root);
  const sites: string[] = [];
  const unguarded: string[] = [];
  for (const file of files) {
    const lines = readFileSync(file, 'utf8').split('\n');
    lines.forEach((line, i) => {
      if (/^\s*(\*|\/\/)/.test(line) || !SYSTEM_CALL.test(line)) return;
      const where = `${file.slice(root.length + 1)}:${i + 1}`;
      sites.push(where);
      if (!lines.slice(Math.max(0, i - 8), i + 1).some((l) => l.includes('withSystemInteraction('))) unguarded.push(where);
    });
  }

  test('no unguarded call, over a scope that is counted', () => {
    // Nine sites on 2026-10-26: three permission asks, the camera hook, the
    // microphone, two settings doors, the fingerprint, the file picker. A
    // count that falls means the pattern stopped seeing them (law 7).
    // Twelve from 2026-10-27 (DEF-FLD-10632, FB-003): the reads screens ask
    // for location themselves — the permission prompt, Android's *Turn on
    // location?* dialog, and the settings door after *Don't ask again*.
    expect(sites).toHaveLength(12);
    expect(unguarded).toEqual([]);
  });
});
