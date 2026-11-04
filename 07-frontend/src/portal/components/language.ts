// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CWP-4440 — the customer portal never applied a language. PO on
//          the running product 2026-09-07: *"Language setting does not work in
//          customer portal"*. `i18n.changeLanguage` was called in exactly ONE
//          place in the whole application — `components/ShellWithSession.tsx`,
//          the STAFF shell — and `portal/PortalApp.tsx` had zero i18n
//          references of any kind.
// Rules:   BR-CWP-105 (the order, and whose language wins) · BR-SHL-041 (the
//          ELEVEN catalogues are ONE registry) · BR-CUS-064 (the account
//          column) · BR-SHL-030 (what the staff shell does with the tenant's)
// Tests:   src/portal/components/language.test.ts
// Impacts: src/portal/components/PortalLanguage.tsx (the only caller of
//          `resolvePortalLanguage`) · src/portal/shell/GuestLanguage.tsx (the
//          dropdown, the only writer of the guest's own choice) ·
//          src/portal/details/Preferences.tsx (`CWP-024`) — the two callers
//          of `offeredLocales`, which is the ONE place the offer is built
//          so the two controls cannot show different lists (DEF-CWP-4442)
// ───────────────────────────────────────────────────────
//
// WHOSE LANGUAGE THE PORTAL IS IN — the whole rule, as one pure function.
//
// ⚠ **PO RULING 2026-09-07, VERBATIM, AND IT IS TWO SENTENCES DOING TWO JOBS:**
// *"a signed-in customer will get their account's own preferred language -
// Signed customer should get their own references. you can also provdie
// language option for gurst customers on top menu as drop down"*.
//
// The order it produces is: **the account's stated preference · a guest's own
// choice in this tab · the tenant's setting · the browser**. The principle
// under it is one sentence and is worth more than the list — **a language the
// person CHOSE beats one the utility chose for them, and a guess comes last.**
// That is why the customer's own preference outranks the utility default (the
// PO's *"their own references"*), why a guest's dropdown choice outranks it
// too, and why the browser — which nobody stated, we only observed — is last.
//
// ⚠ **A GUEST HAS NO FIRST STEP, WHICH IS WHY THIS IS ONE CHAIN AND NOT TWO
// RULES.** Writing a `resolveGuest` beside a `resolveSignedIn` would be two
// places to change the day a fifth source arrives, and the first thing to
// disagree would be the case nobody tests: a person who chose German as a
// guest and then signed in.
//
// ⚠ **NOTHING HERE CALLS `changeLanguage` AND NOTHING HERE READS A QUERY.**
// This file is a pure function over four strings so that every branch of
// `BR-CWP-105` can be asserted without mounting anything — the applier is
// `PortalLanguage.tsx` and is deliberately thin enough to have nothing to test
// but the wire.
import { LOCALE_CODES } from "@/i18n";

/**
 * Where a guest's own choice is kept.
 *
 * ⚠ **`sessionStorage`, NOT `localStorage`, AND NOT AN ACCOUNT COLUMN.** The
 * PO asked for the choice to survive navigation; a guest has no account to
 * store it on, and creating one would mean identifying a stranger who has
 * deliberately not signed in (`BR-CWP-021`). Session storage is exactly the
 * lifetime that describes: every navigation in this tab, gone when the tab
 * closes.
 *
 * ⚠ **THE KEY CARRIES NO TENANT AND DOES NOT NEED TO.** Session storage is
 * already scoped to the origin AND the tab, and a person does not read one
 * utility in German and the next in Korean in the same tab. A tenant segment
 * here would only mean the choice silently resets when they walk between two
 * utilities, which is worse.
 */
export const GUEST_LANGUAGE_KEY = "smartbillhub.portal.language";

/**
 * The code to actually hand `i18n.changeLanguage`, or `null` when this build
 * cannot draw the language asked for.
 *
 * ⚠ **THIS EXISTS BECAUSE THE TWO REGISTRIES ARE NOT THE SAME SIZE AND NEVER
 * WERE.** The server validates `tenant_settings.language` against
 * `SEED_LANGUAGES`, which carries **twelve** codes; the app ships **eleven**
 * catalogues (`BR-SHL-041`). `en-US` is the difference: a real, lawful,
 * saveable tenant setting with no catalogue behind it. Handing it to i18next
 * raw would quietly land on the `en` fallback and look like it worked, which
 * is the good case — the bad case is the same shape with a language that has
 * no fallback anybody wants.
 *
 * Three steps, and each one is a real case rather than defensive padding:
 *
 *  1. **the exact code** — `es-MX` is a catalogue.
 *  2. **its base** — `en-US` → `en`, `es-419` → `es`. This is the
 *     `BR-SHL-042` re-tag arriving from the other direction: the five original
 *     catalogues kept their pre-expansion codes while the picker's registry
 *     names the regional ones, so a stored value can legitimately be either.
 *  3. **a catalogue whose base matches** — `fr` → `fr-FR`, `pt` → `pt-BR`.
 *     This is the BROWSER's step: `navigator.language` is `fr` on plenty of
 *     machines and there is exactly one French catalogue to mean.
 *
 * ⚠ **AND IT ANSWERS *CAN THIS BUILD DRAW IT*, WHICH IS NOT *MAY THE PORTAL
 * OFFER IT* — DO NOT FOLD THE TWO.** The second question is the server's
 * `PORTAL_LOCALES`, it governs the pickers, and `offeredLocales` below is
 * where it is applied. **The Product Owner narrowed it to English and Spanish
 * on 2026-09-07** (`DEF-CWP-4442`, built; this paragraph said *"that constant
 * still carries eleven"* until then) **and this function did not change by one
 * character**, which is the proof the two questions were kept apart: what a
 * build can RENDER is a fact about the bundle, and eleven catalogues are still
 * in it. A customer whose account says German still reads German.
 */
export function supportedLocale(code: string | null | undefined): string | null {
  if (code === null || code === undefined) return null;
  const wanted = code.trim();
  if (wanted === "") return null; // `""` is not a choice — see the seam's own note
  if (LOCALE_CODES.includes(wanted)) return wanted;
  const base = wanted.split("-")[0];
  if (base !== wanted && LOCALE_CODES.includes(base)) return base;
  return LOCALE_CODES.find((one) => one.split("-")[0] === base) ?? null;
}

/**
 * What THIS reader's picker puts in front of them: the offer, plus their own
 * current language when it is neither.
 *
 * ⚠ **PO RULING 2026-09-07, VERBATIM: *"currently in drop down show only 2
 * elnglish and spanish"*** (`DEF-CWP-4442`, implementing their ruling of
 * 2026-09-05). The offer itself is the server's — `PORTAL_LOCALES` — and
 * travels on the wire so that one constant governs BOTH pickers: the guest
 * dropdown in the portal's top menu and the customer's own control on
 * `CWP-024`. Two controls for one setting offering two different lists is how
 * a product tells one person two things.
 *
 * ⚠ **THE THIRD OPTION IS NOT A CONCESSION, IT IS THE DEFECT.** The Product
 * Owner ruled on what the dropdown OFFERS and said nothing about the accounts
 * that already hold `de` or `hi`, and the reading taken — recorded in the
 * decision log of 2026-09-07 rather than re-made here — is that **nobody's
 * stored choice is reset**: taking a setting away from a person who chose it,
 * to solve a problem they do not have, is worse than the untidiness. But a
 * `<select>` whose `value` is not among its `<option>`s renders **BLANK** —
 * no error, no warning, `tsc` green and every `toContain` assertion passing,
 * because the failure is an ABSENCE. So the reader's own language is listed,
 * as what it is, rather than silently dropped.
 *
 * ⚠ **IT IS ONE-WAY BY DESIGN.** Choosing English or Spanish is one click and
 * German then stops being offered to them too, because the third option is
 * derived from what they hold and not from a memory of what they held.
 *
 * ⚠ **THE CODE IS CARRIED THROUGH EXACTLY AS STORED, NOT NORMALISED.** The
 * picker's `value` is the stored string, so answering `en` for a stored
 * `en-US` would leave the control blank over it — this same defect one code
 * along. The one clamp is `supportedLocale`: a language this build cannot
 * DRAW is not offered, because the picker would name it and the page would
 * stay English, which is the failure B14 rule 35's whole family is about.
 */
export function offeredLocales(
  offer: readonly string[],
  current: string | null | undefined,
): string[] {
  const shown = [...offer];
  const wanted = typeof current === "string" ? current.trim() : "";
  if (wanted !== "" && !shown.includes(wanted) && supportedLocale(wanted) !== null) {
    shown.push(wanted);
  }
  return shown;
}

/** The four sources, in the order `BR-CWP-105` ranks them. */
export interface PortalLanguageSources {
  /** `accounts.preferred_language`, folded by the server. `null` for a guest,
   *  and `null` when a login's accounts disagree. */
  readonly account: string | null | undefined;
  /** What this guest picked from the top menu in this tab. */
  readonly guestChoice: string | null | undefined;
  /** `tenant_settings.language` — the utility's own default. */
  readonly tenant: string | null | undefined;
  /** `navigator.language`. A guess, so it is last. */
  readonly browser: string | null | undefined;
}

/**
 * `BR-CWP-105`'s chain, whole, in the order the Product Owner ruled.
 *
 * Returns the code to apply, or `null` when not one of the four names a
 * language this build carries — and `null` means **apply nothing**, leaving
 * i18next at its own `en` default. It does not mean *fall back to English*,
 * and the difference matters: applying English over a tenant whose setting has
 * simply not loaded yet would make the load order visible to the customer as a
 * flicker, and would be `DEF-SHL-3964`'s plausible-default trap wearing a hat.
 */
export function resolvePortalLanguage(sources: PortalLanguageSources): string | null {
  for (const candidate of [
    sources.account,
    sources.guestChoice,
    sources.tenant,
    sources.browser,
  ]) {
    const drawable = supportedLocale(candidate);
    if (drawable !== null) return drawable;
  }
  return null;
}

/**
 * What this guest picked, or `null`.
 *
 * ⚠ **EVERY READ IS IN A `try`, AND THAT IS NOT SUPERSTITION.** Safari in
 * private browsing and any browser with site data blocked THROW on
 * `sessionStorage` access rather than returning empty — and this runs on the
 * portal's root, so an exception here is a blank page for a guest whose only
 * mistake was a privacy setting. The honest answer in that world is *this
 * person has no stored choice*, which is exactly `null`.
 */
export function readGuestLanguage(): string | null {
  try {
    return window.sessionStorage.getItem(GUEST_LANGUAGE_KEY);
  } catch {
    return null;
  }
}

/** Remember this guest's choice for the life of the tab. Silent on refusal,
 *  for the reason `readGuestLanguage` gives: a privacy setting must cost them
 *  the memory, never the page. */
export function writeGuestLanguage(code: string): void {
  try {
    window.sessionStorage.setItem(GUEST_LANGUAGE_KEY, code);
  } catch {
    /* nothing to do: the language still applies for this page */
  }
}
