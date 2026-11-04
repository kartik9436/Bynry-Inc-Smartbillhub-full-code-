// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-071 TC-7 (the language table) · US-CWP-072 TC-8 (the line
//           that says which language you are reading)
// Rules:    B14 rule 35 (⚠ a catalogue is written in its own language — and a
//           LANGUAGE'S OWN NAME is not a catalogue line at all. *Deutsch* is
//           *Deutsch* on a French screen and on a Korean one, because that is
//           what its speakers call it; eleven catalogues each holding eleven
//           copies of the same eleven strings would be 121 lines that can only
//           ever be identical, and 110 of them would read to `G15` as English
//           pasted in untranslated — which is exactly what they would be)
// Tests:    src/features/tenancy/SettingsPortalHelp.test.tsx
// ───────────────────────────────────────────────────────
/**
 * `"es-MX"` → *Español (México)*, in that language's own words.
 *
 * ⚠ **CAPITALISED, AND THAT IS NOT A STYLE PREFERENCE.** `Intl` returns
 * *français (France)* — correct running prose in French, where language names
 * are lower case — but this string is a LABEL in a table of languages, and a
 * label starts with a capital in every one of the eleven whose script has case.
 * Scripts without case (Hindi, Japanese, Korean) are untouched, because
 * `toUpperCase` on a caseless character returns the character.
 */
export function languageName(code: string): string {
  try {
    const display = new Intl.DisplayNames([code], { type: "language" });
    const name = display.of(code);
    if (name === undefined) return code;
    return name.charAt(0).toLocaleUpperCase(code) + name.slice(1);
  } catch {
    // A runtime without `DisplayNames`, or a code it does not know: the code
    // itself is honest and unambiguous, and never a wrong language's name.
    return code;
  }
}


/**
 * The language to ASK FOR an answer in — the visitor's BROWSER setting.
 *
 * ⚠ **NOT `i18n.language`, AND THE DIFFERENCE IS THE WHOLE OF `BR-CWP-094`'s
 * DEMO.** A guest has no account and no stored preference; their browser's own
 * setting is the only honest statement of what they read.
 *
 * ⚠ **THE SENTENCE THIS PARAGRAPH USED TO OPEN WITH WENT STALE ON 2026-09-07
 * AND IS CORRECTED RATHER THAN LEFT (`DEF-CWP-4440`).** It read: *"The app
 * pins `lng: en` because no language switcher exists yet, so `i18n.language`
 * is English for a French visitor as much as for anybody else"*. That was true
 * when it was written and is **no longer true of the portal**: `PortalLanguage`
 * now applies `BR-CWP-105`'s chain at the portal's root and the guest frame
 * carries a picker, so `i18n.language` on a portal screen is a real answer.
 * Hard-won law 1 — a comment describing a mechanism is not the mechanism, and
 * one whose premise has moved is worse than none.
 *
 * **THE FUNCTION'S BEHAVIOUR IS DELIBERATELY UNCHANGED.** This asks *what
 * language should this ANSWER be written in*, which is a question about
 * published CONTENT (`BR-CWP-094`), not about the chrome around it. So a guest
 * reading Spanish chrome on a French browser is still offered a French help
 * answer, and told when there is not one. Making the two agree is a content
 * decision beyond `DEF-CWP-4440` and is recorded as its residual in the
 * decision log of 2026-09-07 rather than taken quietly here.
 */
export function readerLocale(fallback: string): string {
  if (typeof navigator !== "undefined" && typeof navigator.language === "string" && navigator.language) {
    return navigator.language;
  }
  return fallback;
}

/**
 * A catalogue sentence that names a language in that language's own words,
 * cut where the name goes so the name can be marked with its own `lang` —
 * *"…, la ves en <span lang="en">English</span>."*
 *
 * ⚠ **`DEF-CWP-10561` (WCAG 3.1.2, tester F-05).** The name is an endonym on
 * purpose (see `languageName`), which makes it a word in ANOTHER language in
 * the middle of the reader's sentence; unmarked, a Spanish voice reads
 * *English* as Spanish. The catalogue sentence is not split or re-keyed: it is
 * rendered with a marker where the name goes and cut at the marker, so the
 * words on screen are exactly what they were and all eleven catalogues stay
 * as written.
 */
export function sentenceNamingLanguage(
  sentence: (marker: string) => string,
  code: string,
): { before: string; name: string; after: string } {
  const marker = "\u0000";
  const whole = sentence(marker);
  const at = whole.indexOf(marker);
  if (at === -1) return { before: whole, name: "", after: "" };
  return { before: whole.slice(0, at), name: languageName(code), after: whole.slice(at + marker.length) };
}
