/**
 * THE GUARD: nothing unsent is ever discarded to solve an auth problem
 * (Security tab §1, *"There is no state in which captured work is thrown away
 * to resolve an auth problem"*; R60, R64, R113, R115).
 *
 * Every auth transition the session layer has is run against an outbox
 * holding three technicians' unsent work, and the exact set of unsent rows is
 * compared before and after. A transition that loses one row fails here,
 * naming the transition.
 *
 * RED FIRST (law 7). On 2026-10-21 `SessionManager.signOut` was given the
 * defect this guard exists for — one line,
 * `(this.deps.outbox as unknown as { purgeTechnician(id: string): void }).purgeTechnician(tech.technicianId);`
 * — and `npx jest tests/session` (the suite's own entry point) went 3 failed,
 * 21 passed, on exactly the transitions that pass through it:
 *
 *     ✕ sign-out (FF-53 "Sign out anyway") keeps every unsent row
 *     ✕ sign-out with no signal keeps every unsent row
 *         - Expected  - 3
 *         -   "tech-dana:d1",
 *         -   "tech-dana:d2",
 *         -   "tech-dana:p1",
 *     ✕ (sessionManager.test.ts) a technician never sees another’s unsent
 *       work as their own — Marco's own row was gone after his sign-out
 *
 * With the line removed it is 24 of 24 green again.
 *
 * The member check below was proved the same way: adding
 * `discardUnsent(technicianId: string): Promise<void>;` to `OutboxPort` failed
 * it with `+ "discardUnsent"`.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

import { HOUR_MS, MINUTE_MS } from '../../src/security/clock';
import { type SessionManager } from '../../src/session/sessionManager';
import { makeHandset, PEOPLE, signIn } from './fakes';

type Handset = ReturnType<typeof makeHandset>;

async function seeded(): Promise<Handset> {
  const h = makeHandset();
  await signIn(h.session, 'r.patel');
  await signIn(h.session, 'm.chen');
  await signIn(h.session, 'd.ortiz');
  h.outbox.add('tech-dana', 'item', 'd1');
  h.outbox.add('tech-dana', 'item', 'd2');
  h.outbox.add('tech-dana', 'photo', 'p1');
  h.outbox.add('tech-marco', 'item', 'm1');
  h.outbox.add('tech-patel', 'item', 'x1');
  return h;
}

const TRANSITIONS: Array<[string, (h: Handset, s: SessionManager) => Promise<unknown>]> = [
  ['sign-out (FF-53 "Sign out anyway")', (_h, s) => s.signOut()],
  [
    'sign-out with no signal',
    async (h, s) => {
      h.api.online = false;
      await s.signOut();
    },
  ],
  ['access token expiry, refresh with no signal', async (h, s) => {
    h.api.online = false;
    h.clock.advance(2 * HOUR_MS);
    await s.refresh();
  }],
  ['capture credential expiry (a week off)', async (h, s) => {
    h.api.online = false;
    h.clock.advance(7 * 24 * HOUR_MS + HOUR_MS);
    await s.refresh();
    s.tick();
  }],
  ['auto-lock after five minutes idle', async (h, s) => {
    h.clock.advance(6 * MINUTE_MS);
    s.tick();
  }],
  ['lock after five minutes away', async (h, s) => {
    s.onBackground();
    h.clock.advance(6 * MINUTE_MS);
    s.onForeground();
  }],
  ['switch technician', (_h, s) => s.switchTo('tech-marco', PEOPLE['m.chen']!.password)],
  ['a failed switch (wrong password)', (_h, s) => s.switchTo('tech-marco', 'wrong').catch(() => undefined)],
  ['remote sign-out from the back office', (_h, s) => s.remoteSignOut('tech-dana')],
  ['cold restart', (h) => h.build().restore()],
];

describe('nothing unsent is ever discarded by an auth transition', () => {
  test.each(TRANSITIONS)('%s keeps every unsent row', async (_name, transition) => {
    const h = await seeded();
    const before = h.outbox.unsentKeys();
    expect(before).toHaveLength(5);
    await transition(h, h.session);
    expect(h.outbox.unsentKeys()).toEqual(before);
  });

  test('the session layer’s only door into the outbox has exactly two members, neither a delete', () => {
    // Read the interface as written, so adding a third member — a purge, a
    // discard, a "clear on sign-out" — fails here and has to be argued.
    const source = readFileSync(join(__dirname, '../../src/session/outboxPort.ts'), 'utf8');
    const body = /export interface OutboxPort \{([\s\S]*?)\n\}/.exec(source)?.[1] ?? '';
    const members = [...body.matchAll(/^\s{2}(\w+)\s*\(/gm)].map((m) => m[1]);
    expect(members).toEqual(['unsentCounts', 'dropMirror']);
  });
});
