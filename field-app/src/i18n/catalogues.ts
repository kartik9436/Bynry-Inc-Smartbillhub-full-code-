/**
 * The field app's words, read from the SAME eleven catalogues as the web app
 * (decision log 2026-10-21, conflict #3: *"Field-app words carry their own
 * `field.*` prefix … through the same tool"*).
 *
 * ⚠ **ONLY `field.*` KEYS ARE TAKEN — AND THE SERVER'S `work.*` SENTENCES.** A web catalogue holds ~25,000 keys and
 * the field app needs a few hundred; the rest is the web's and never reaches a
 * field screen, so a shared key cannot be re-worded under the field app by a
 * web lane, or the other way round. The one other family taken is `work.*`:
 * the SERVER's own words for what it refuses (`{message_key}` on a refused
 * item, e.g. `work.mobile.accept_the_job_first` → *"Accept the job first."*),
 * which the server says the handset renders as the staff app would
 * (`apps/work/sync._refused`). Without them FF-50 showed a refusal as its raw
 * code (DEF-FLD-10579). They are read, never re-worded here.
 *
 * ⚠ **THE WHOLE CATALOGUE IS STILL IN THE BUNDLE.** Metro bundles every
 * `require` it can see, so the eleven files (~20 MB of JSON) ship with the
 * app even though one is parsed at a time — they are required lazily, inside a
 * function, so start-up only parses the one in use. Cutting the bundle to the
 * `field.*` slice needs a build step that writes it out, which is reported
 * rather than invented here.
 *
 * English has a second source that is always present:
 * `field-keys.en.json`, the field app's own new keys, kept here until the
 * coordinator fans them into the eleven catalogues with
 * `10-scripts/i18n_fanin.py`. The shared English wins where both have a key,
 * because after the fan-in that is the reviewed copy.
 */
import fieldKeysEn from './field-keys.en.json';
import acceptanceKeys from './keys/acceptance.en.json';
import closingKeys from './keys/closing.en.json';
import findingsKeys from './keys/findings.en.json';
import gettingInKeys from './keys/gettingIn.en.json';
import meKeys from './keys/me.en.json';
import onSiteKeys from './keys/onSite.en.json';
import raiseKeys from './keys/raise.en.json';
import readsKeys from './keys/reads.en.json';
import refusalKeys from './keys/refusals.en.json';
import releaseKeys from './keys/release.en.json';
import tabletKeys from './keys/tablet.en.json';
import theDayKeys from './keys/theDay.en.json';
import theJobKeys from './keys/theJob.en.json';
import { type LanguageCode } from './languages';

export type Catalogue = Record<string, string>;

export const FIELD_PREFIX = 'field.';
/** The server's refusal sentences (DEF-FLD-10579) — see the header. */
export const SERVER_PREFIX = 'work.';

/* eslint-disable @typescript-eslint/no-require-imports */
const LOADERS: Record<LanguageCode, () => unknown> = {
  en: () => require('../../../07-frontend/src/i18n/locales/en.json'),
  de: () => require('../../../07-frontend/src/i18n/locales/de.json'),
  es: () => require('../../../07-frontend/src/i18n/locales/es.json'),
  'es-MX': () => require('../../../07-frontend/src/i18n/locales/es-MX.json'),
  'fr-FR': () => require('../../../07-frontend/src/i18n/locales/fr-FR.json'),
  hi: () => require('../../../07-frontend/src/i18n/locales/hi.json'),
  'id-ID': () => require('../../../07-frontend/src/i18n/locales/id-ID.json'),
  'it-IT': () => require('../../../07-frontend/src/i18n/locales/it-IT.json'),
  'ja-JP': () => require('../../../07-frontend/src/i18n/locales/ja-JP.json'),
  'ko-KR': () => require('../../../07-frontend/src/i18n/locales/ko-KR.json'),
  'pt-BR': () => require('../../../07-frontend/src/i18n/locales/pt-BR.json'),
};
/* eslint-enable @typescript-eslint/no-require-imports */

/** The `field.*` slice of a flat catalogue — plus, when asked, the server's `work.*` sentences. */
export function fieldSlice(catalogue: unknown, withServer = false): Catalogue {
  const out: Catalogue = {};
  if (catalogue == null || typeof catalogue !== 'object') return out;
  for (const [key, value] of Object.entries(catalogue as Record<string, unknown>)) {
    const wanted = key.startsWith(FIELD_PREFIX) || (withServer && key.startsWith(SERVER_PREFIX));
    if (wanted && typeof value === 'string' && value.trim() !== '') {
      out[key] = value;
    }
  }
  return out;
}

/** The field app's own English keys, not yet fanned in. */
/** The shell's keys plus one file per screen wave (`keys/<wave>.en.json`), so waves never edit the same file. */
export const FIELD_KEYS_EN: Catalogue = {
  ...(fieldKeysEn as Catalogue),
  ...(gettingInKeys as Catalogue),
  ...(theDayKeys as Catalogue),
  ...(theJobKeys as Catalogue),
  ...(onSiteKeys as Catalogue),
  ...(closingKeys as Catalogue),
  ...(raiseKeys as Catalogue),
  ...(meKeys as Catalogue),
  ...(readsKeys as Catalogue),
  ...(findingsKeys as Catalogue),
  ...(tabletKeys as Catalogue),
  ...(releaseKeys as Catalogue),
  ...(acceptanceKeys as Catalogue),
  // The reads door's refusals (`work.mobile.reads.<reason>` on the server), in
  // the handset's words — `screens/me/dbData.refusalKeyOf` maps one to the other.
  ...(refusalKeys as Catalogue),
};

export type CatalogueSource = (code: LanguageCode) => Catalogue;

/** The shipped source: the shared catalogue's `field.*` slice, English topped up from `field-keys.en.json`. */
export const sharedCatalogues: CatalogueSource = (code) => {
  const shared = fieldSlice(LOADERS[code](), true);
  return code === 'en' ? { ...FIELD_KEYS_EN, ...shared } : shared;
};
