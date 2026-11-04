// ── Trace ──────────────────────────────────────────────
// Story:   DEF-CWP-4440 — PO ruling 2026-09-07, verbatim: *"you can also
//          provdie language option for gurst customers on top menu as drop
//          down"*. New scope, ruled into the defect rather than deferred.
// Defect:  DEF-CWP-4442 — PO ruling 2026-09-07, verbatim: *"currently in drop
//          down show only 2 elnglish and spanish"*. The options are the
//          SERVER's offer now, off the front payload, and not the catalogue
//          registry — the fold BR-CWP-105 forbids, undone.
// Rules:   BR-CWP-105 (a guest's own choice outranks the utility's default and
//          is kept for the tab) · B14 rule 8 (a real `<select>`) · B14 rule 31
//          (no database id — and a locale code is one) · B14 rule 35 (a
//          language is named in its own language) · US-CWP-001 TC-3 (portal
//          off → no nav, so no control)
// Tests:   src/portal/shell/GuestLanguage.dom.test.tsx
// Impacts: src/portal/shell/GuestFrame.tsx (its only caller)
// ───────────────────────────────────────────────────────
import { useTranslation } from "react-i18next";

import { announce, refocus } from "../components/a11y";
import { languageName } from "../components/languageName";
import { offeredLocales, supportedLocale, writeGuestLanguage } from "../components/language";

/**
 * The guest's own language picker, in the portal's top menu.
 *
 * ⚠ **IT CHANGES THE PAGE ITSELF RATHER THAN ASKING SOMETHING ELSE TO.** This
 * is hard-won law 2's mirror — a live-looking control over nothing — and the
 * portal shipped eight of those on one page in September (`DEF-CWP-3925`). So
 * `onChange` calls `changeLanguage` here and now: the words on screen turn
 * over before the customer's finger leaves the mouse, with no round trip and
 * nothing to fail. Writing the choice down is the second act, and the applier
 * at the portal's root reads it back on every later render so a navigation
 * cannot undo it (`BR-CWP-105` step two).
 *
 * ⚠ **EACH LANGUAGE IS NAMED IN ITS OWN LANGUAGE — *Español (México)*,
 * *Deutsch*, *日本語 (日本)* — AND NEVER AS `es-MX`.** A locale code is an
 * internal identifier on a customer's screen (B14 rule 31), and a list of
 * ENGLISH names would be unreadable to the one person who needs to use it:
 * somebody who cannot read the page they are looking at (B14 rule 35).
 * `languageName` is the same function the signed-in picker on `CWP-024`
 * already uses, so the two lists name the same language the same way.
 *
 * ⚠ **NO NEW CATALOGUE STRING WAS MINTED FOR THIS.** The accessible name
 * reuses `portal.preferences.languageTitle` — *LANGUAGE · IDIOMA · SPRACHE ·
 * 言語* — which is already human-written in all eleven catalogues for the
 * picker this control mirrors. `G15` counts 182 untranslated values and this
 * control moved that number by zero, which is the only acceptable answer when
 * a fix has no copy of its own to write.
 *
 * ⚠ **THE OPTIONS ARE THE SERVER'S OFFER, AND THEY WERE THE CATALOGUES UNTIL
 * 2026-09-07 (`DEF-CWP-4442`).** This list read `LOCALE_CODES`, which answers
 * *what can this build DRAW* — the fold `BR-CWP-105` says never to make. The
 * question a picker asks is *what may the portal OFFER*, the server's
 * `PORTAL_LOCALES` is the one answer to it, and the Product Owner narrowed it
 * to two: *"currently in drop down show only 2 elnglish and spanish"*. It
 * rides on `GET portal/public/front` because the guest half of the portal has
 * no other payload, which is the same door the tenant's own language uses.
 *
 * ⚠ **`offer` IS REQUIRED AND NOT OPTIONAL, AND THAT IS HARD-WON LAW 2.** An
 * optional prop with a default nothing passes is a control drawing a list the
 * server never sent, and it renders, and every test passes. The frame reads
 * `front.locales` and hands it down; there is no other way to build this
 * control.
 *
 * ⚠ **A READER ALREADY ON A THIRD LANGUAGE SEES IT LISTED.** `offeredLocales`
 * is the one place that rule lives — the same function `CWP-024`'s picker
 * calls — so the guest control and the signed-in one cannot show two
 * different lists. Its docstring carries the reasoning; the short version is
 * that a `<select>` listing two options over a stored third renders blank.
 */
export function GuestLanguage(props: { readonly offer: readonly string[] }) {
  const { t, i18n } = useTranslation();
  // The value has to be one of the options or the `<select>` draws blank.
  // `i18n.language` can carry a region i18next resolved from a fallback, so it
  // goes through the same mapper everything else does.
  const current = supportedLocale(i18n.language) ?? "en";
  const options = offeredLocales(props.offer, current);
  // ⚠ **A UTILITY THAT OFFERS ONE LANGUAGE GETS NO PICKER AT ALL.** The
  // wireframe's `s2` states it as a screen state and gives the reason in five
  // words — *"a chooser with one option is furniture"* — and it is `BR-CWP-093`
  // (nothing empty ever appears) one control along: a `<select>` that cannot
  // change anything is a control a person opens once, learns nothing from, and
  // then distrusts. Most tenants are in exactly this state; Pine Hill offers
  // two, which is why nobody had seen the one-option case.
  //
  // ⚠ **IT IS `options`, NOT `props.offer`, THAT DECIDES.** A reader whose own
  // language is not in the utility's offer has a real second option — the one
  // `offeredLocales` adds so their `<select>` does not draw blank — and hiding
  // the control from THEM would strand them on a language they never chose.
  if (options.length < 2) return null;
  return (
    <select
      // F-17 (`DEF-CWP-10553`, ruled 2026-10-23): switches on every pick as
      // before; the label says so, focus returns here once the page has been
      // redrawn in the new language, and the change is announced IN that
      // language — *"Página en español"*.
      aria-label={t("portal.shell.languageChangesPage")}
      className="h-9 border border-field-border bg-[white] px-3 text-body text-neutral-900"
      data-guest-language="select"
      value={current}
      onChange={(event) => {
        const code = event.target.value;
        writeGuestLanguage(code);
        void i18n.changeLanguage(code).then(() =>
          refocus('select[data-guest-language="select"]', () =>
            announce(i18n.t("portal.a11y.pageLanguage", { lng: code })),
          ),
        );
      }}
    >
      {options.map((code) => (
        // DEF-CWP-10561 (WCAG 3.1.2): each name is written in its own language.
        <option key={code} value={code} lang={code}>
          {languageName(code)}
        </option>
      ))}
    </select>
  );
}
