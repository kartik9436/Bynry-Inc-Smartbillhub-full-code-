/**
 * The Settings line — T-75, R72 (FF-51 Settings).
 *
 * One line saying diagnostics are on and what they leave out. B14 rule 33: a
 * FACT is at most six words, and RATIONALE is zero words on screen — so this
 * says what is true and never why.
 *
 * ⚠ The FF-51 image as captured ends above this line (it is cut off below
 * "Bigger text"), so the words below are this lane's, not the drawing's. The
 * screen lane should check them against the full board and the i18n lane owns
 * the catalogue; the key is returned so neither has to change this file.
 */
export interface DiagnosticsLine {
  /** i18n key for the catalogue. */
  key: 'settings.diagnostics.on' | 'settings.diagnostics.off';
  /** English, for the catalogue's source and for tests. */
  text: string;
}

export function diagnosticsLine(enabled = true): DiagnosticsLine {
  return enabled
    ? { key: 'settings.diagnostics.on', text: 'Diagnostics on. No customer data.' }
    : { key: 'settings.diagnostics.off', text: 'Diagnostics off.' };
}
