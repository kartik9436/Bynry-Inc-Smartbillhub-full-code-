/**
 * DEF-FLD-10616 — the phone's dispatch-state words ARE the web's words, in
 * every language (decision log 2026-10-26, PO *"use web words"*).
 *
 * The phone (`field.job.state.*`, and the map legend's two rows that name a
 * state) and the web (`work.orders.dispatch.<state>`) were translated
 * separately, so German read *Erledigt* on the phone and *Abgeschlossen* on the
 * web for the same job. G15 checks every catalogue holds the same KEYS and could
 * never see it. This compares the WORDS: for each of the seven server states,
 * the key `statusLook` really shows (so re-pointing a state is compared too),
 * against the web key for that state, in all eleven catalogues — and English's
 * own copy in `keys/theDay.en.json`. It counts what it compared, so a test that
 * silently read nothing cannot pass (law 7).
 */
import { readdirSync, readFileSync } from 'fs';
import { join } from 'path';

import theDayKeys from '../../src/i18n/keys/theDay.en.json';
import { LEGEND, statusLook } from '../../src/screens/theDay/jobStatus';

const LOCALES = join(__dirname, '../../../07-frontend/src/i18n/locales');
const STATES = ['queued', 'scheduled', 'en_route', 'on_site', 'on_hold', 'complete', 'cancelled'] as const;
/** The legend rows that name ONE state (`inProgress` names three and is not a state word). */
const LEGEND_STATE: Record<string, (typeof STATES)[number]> = { scheduled: 'scheduled', queued: 'queued' };

const files = readdirSync(LOCALES).filter((name) => name.endsWith('.json'));

function pairs(): Array<[string, string]> {
  const out: Array<[string, string]> = [];
  for (const state of STATES) {
    const key = statusLook(state).labelKey;
    expect(key).not.toBeNull();
    out.push([key as string, `work.orders.dispatch.${state}`]);
  }
  for (const row of LEGEND) {
    const state = LEGEND_STATE[row.key];
    if (state) out.push([row.labelKey, `work.orders.dispatch.${state}`]);
  }
  return out;
}

test('all eleven catalogues are compared', () => {
  expect(files.sort()).toEqual(
    ['de', 'en', 'es', 'es-MX', 'fr-FR', 'hi', 'id-ID', 'it-IT', 'ja-JP', 'ko-KR', 'pt-BR'].map((l) => `${l}.json`).sort(),
  );
});

test.each(files)('%s: every phone state word is the web word', (file) => {
  const catalogue = JSON.parse(readFileSync(join(LOCALES, file), 'utf8')) as Record<string, string>;
  const compared = pairs();
  expect(compared).toHaveLength(9);
  const differ = compared
    .filter(([phone, web]) => catalogue[phone] !== catalogue[web] || !catalogue[web])
    .map(([phone, web]) => `${phone}=${JSON.stringify(catalogue[phone])} but ${web}=${JSON.stringify(catalogue[web])}`);
  expect(differ).toEqual([]);
});

test("the phone's own English copy carries the web's English words", () => {
  const en = JSON.parse(readFileSync(join(LOCALES, 'en.json'), 'utf8')) as Record<string, string>;
  const own = theDayKeys as Record<string, string>;
  const differ = pairs()
    .filter(([phone, web]) => own[phone] !== en[web])
    .map(([phone, web]) => `${phone}=${JSON.stringify(own[phone])} but ${web}=${JSON.stringify(en[web])}`);
  expect(differ).toEqual([]);
});
