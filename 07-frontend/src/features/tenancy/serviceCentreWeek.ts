// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-074 (EP-CWP-12) — the week, in the reader's own language.
// Rules:    B14 rule 35 (⚠ a catalogue is written in its own language — a
//           weekday NAME is not a catalogue line at all: `Intl` knows every
//           language's own word for Thursday, and eleven hand-written lists of
//           seven days would be eleven chances to be wrong)
// Tests:    src/features/tenancy/SettingsServiceCentres.test.tsx
// ───────────────────────────────────────────────────────
/** Monday = 0 … Sunday = 6 — the server's `date.weekday()`, named natively. */
export function weekdayLabel(day: number, language: string): string {
  // 2024-01-01 was a Monday, so `1 + day` lands on the wanted weekday.
  return new Intl.DateTimeFormat(language, { weekday: "long" }).format(new Date(2024, 0, 1 + day));
}
