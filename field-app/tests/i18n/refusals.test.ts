/**
 * @jest-environment node
 *
 * The reads door refuses an item back to the reader with a machine reason and
 * `message_key: work.mobile.reads.<reason>` (`06-backend/apps/metering/
 * field_reads.py`, 2026-10-21). Those keys are in NO catalogue yet — the
 * coordinator fans them out — so the handset carries its own words for each
 * (`src/i18n/keys/refusals.en.json`, `field.reads.refused.<reason>`) and FF-50
 * shows them (`screens/me/dbData.refusalKeyOf`).
 *
 * This reads the server's file for every reason it can answer, so a reason
 * added there goes RED here until the handset has words for it — and prints
 * how many it found, so a scan that found nothing cannot pass (law 7).
 * Proved RED (lane INTEGRATE-2): with `photo_id_reused` removed from the JSON,
 * this failed naming it.
 */
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { FIELD_KEYS_EN, sharedCatalogues } from '../../src/i18n/catalogues';
import { refusalKeyOf } from '../../src/screens/me/dbData';

const READS = resolve(__dirname, '../../../06-backend/apps/metering/field_reads.py');
const PHOTOS = resolve(__dirname, '../../../06-backend/apps/metering/field_read_photos.py');

function serverReasons(): string[] {
  const reads = readFileSync(READS, 'utf8');
  const photos = readFileSync(PHOTOS, 'utf8');
  const found = new Set<string>();
  for (const m of reads.matchAll(/^HELD_[A-Z_]+ = "([a-z0-9_]+)"/gm)) found.add(m[1]!);
  for (const m of reads.matchAll(/_refused\([^,]+, [^,]+, "([a-z0-9_]+)"/g)) found.add(m[1]!);
  for (const m of photos.matchAll(/DeclarationRefused\("([a-z0-9_]+)"/g)) found.add(m[1]!);
  return [...found].sort();
}

test('every reason the reads door can refuse with has the handset’s words', () => {
  const reasons = serverReasons();
  console.log(`refusals: ${reasons.length} reasons read from the reads door`);
  expect(reasons.length).toBeGreaterThanOrEqual(27);
  const missing = reasons.filter((r) => !FIELD_KEYS_EN[`field.reads.refused.${r}`]);
  expect(missing).toEqual([]);
});

test('a reads refusal maps to the handset key; any other server key is shown as itself (DEF-FLD-10579)', () => {
  expect(refusalKeyOf(JSON.stringify({ reason: 'unit_missing', message_key: 'work.mobile.reads.unit_missing' }))).toBe(
    'field.reads.refused.unit_missing',
  );
  expect(refusalKeyOf(JSON.stringify({ detail: { message_key: 'work.mobile.reads.photo_id_reused' } }))).toBe(
    'field.reads.refused.photo_id_reused',
  );
  // Before DEF-FLD-10579 these were null, and FF-50 showed `accept_the_job_first`.
  expect(refusalKeyOf(JSON.stringify({ message_key: 'work.safety.locked' }))).toBe('work.safety.locked');
  expect(
    refusalKeyOf(JSON.stringify({ reason: 'accept_the_job_first', message_key: 'work.mobile.accept_the_job_first' })),
  ).toBe('work.mobile.accept_the_job_first');
  // A whole-request refusal stores the server's body (`receipts.applyBatchFailure`).
  expect(refusalKeyOf(JSON.stringify({ status: 409, body: { message_key: 'work.mobile.job_already_declined' } }))).toBe(
    'work.mobile.job_already_declined',
  );
  expect(refusalKeyOf(JSON.stringify({ message: 'refused' }))).toBeNull();
  expect(refusalKeyOf(null)).toBeNull();
});

test('the server’s refusal sentences are in every catalogue the handset loads, so FF-50 shows words', () => {
  for (const code of ['en', 'de', 'es', 'fr-FR', 'ja-JP'] as const) {
    const words = sharedCatalogues(code);
    for (const key of ['work.mobile.accept_the_job_first', 'work.mobile.job_already_declined', 'work.mobile.decline_reason_required']) {
      expect([code, key, typeof words[key]]).toEqual([code, key, 'string']);
    }
  }
  expect(sharedCatalogues('en')['work.mobile.accept_the_job_first']).toBe('Accept the job first.');
}, 60_000);
