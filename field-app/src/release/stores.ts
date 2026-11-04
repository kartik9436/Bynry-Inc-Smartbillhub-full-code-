/**
 * THE TWO STORE ADDRESSES OF THE NATIVE FIELD APP — empty today, on purpose.
 *
 * The field app's own copy of `07-frontend/src/features/identity/fieldAppStores.ts`
 * (`FIELD_APP_STORE_URLS`), for the *Update the app* screen's button. The
 * addresses come from the store consoles once the listings exist (App Store
 * Connect → the app's Apple ID; Play Console → the package name) — they are
 * the PO's to supply, never guessed. Fill BOTH files in the same commit.
 *
 * While an address is empty the screen shows the instruction without a
 * button: a button that opens nothing is a dead control (law 2's mirror).
 */
export const FIELD_APP_STORE_URLS = {
  /** e.g. `https://apps.apple.com/app/id<Apple ID>` — supplied by the PO. */
  appStore: '',
  /** e.g. `https://play.google.com/store/apps/details?id=<package>` — supplied by the PO. */
  googlePlay: '',
} as const;

export interface StoreUrls {
  appStore: string;
  googlePlay: string;
}

/** The store this handset updates from, or null when its address is not known yet. */
export function storeUrlFor(platform: string | null | undefined, urls: StoreUrls = FIELD_APP_STORE_URLS): string | null {
  const url = platform === 'ios' ? urls.appStore : platform === 'android' ? urls.googlePlay : '';
  return url.trim() !== '' ? url.trim() : null;
}
