/**
 * DEF-FLD-10623 — FF-50 has a word for EVERY kind the outbox can hold.
 *
 * A refused accept read as the bare `job_accept`, as `raise` had before it
 * (DEF-FLD-10603): `KIND_KEY` listed the kinds somebody had tested, and the
 * screen fell back to the raw kind for the rest. This walks every capturable
 * kind — the job sync kinds, the route kinds, every own-door kind
 * (`DOOR_KINDS`) and the kinds still waiting for a door — and fails on any
 * with no word in English.
 */
import { FIELD_KEYS_EN } from '../../../src/i18n/catalogues';
import { KIND_KEY } from '../../../src/screens/me/SyncScreen';
import { DOOR_KINDS } from '../../../src/sync/doors';
import { CAPTURABLE_KINDS, JOB_SYNC_KINDS, UNROUTED_KINDS } from '../../../src/sync/outbox';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

test('the capturable list holds every sync kind, every door kind and every waiting kind', () => {
  for (const k of [...JOB_SYNC_KINDS, ...DOOR_KINDS, ...UNROUTED_KINDS, 'route_read', 'route_finding', 'field_asset']) {
    expect(CAPTURABLE_KINDS).toContain(k);
  }
  // Printed so a list that silently shrank cannot pass (law 7).
  expect(CAPTURABLE_KINDS.length).toBeGreaterThanOrEqual(20);
});

test.each([...CAPTURABLE_KINDS])('%s has a word on FF-50', (kind) => {
  const key = (KIND_KEY as Record<string, string | undefined>)[kind];
  expect(key).toBe(`field.ff50.kind.${kind}`);
  const words = (FIELD_KEYS_EN as Record<string, string | undefined>)[key!];
  expect(typeof words).toBe('string');
  expect(words!.trim()).not.toBe('');
  expect(words).not.toBe(kind);
});
